"""Licence Approving Officer routes.

A distinct OFFICER role (separate from APPLICANT/INSPECTOR/ADMIN). Officers are
created by demo seeding and receive applications via deterministic auto-routing
(routing.py). Security model:

  * An officer only ever sees applications ASSIGNED to them
    (application_assignments.officer_id == current officer).
  * An officer can only ever act on applications whose licence type they are
    authorised for, i.e. those routed to them by the engine.
  * Every action is persisted (status history + audit log + notification) and
    broadcast live over SSE so the applicant's timeline updates in real time.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from .. import db
from ..models import (
    Application, ApplicationAssignment, ApplicationStatusHistory, AuditLog,
    Business, Certificate, Inspection, Notification, Officer, Renewal, User,
    gen_id, now,
)
from ..services.realtime import publish
from datetime import timedelta, timezone
import uuid

officer_bp = Blueprint('officer', __name__)

# Statuses an officer may action directly from their inbox.
ACTIONABLE = ('DECISION_PENDING', 'INSPECTION_COMPLETED', 'INSPECTION_PASSED')

TERMINAL = ('APPROVED', 'REJECTED', 'EXPIRED')

QUEUED = ('DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'DOCUMENT_VALIDATION',
          'CORRECTION_REQUIRED', 'ADDITIONAL_DOCUMENTS_REQUIRED')

INSPECTION_STATES = ('INSPECTION_REQUIRED', 'INSPECTION_SCHEDULED',
                     'INSPECTION_STARTED', 'INSPECTION_COMPLETED')

def get_current_user():
    from .utils import get_current_user as _shared
    return _shared()

def _add_audit(application_id, user_id, action, details=''):
    db.session.add(AuditLog(application_id=application_id, user_id=user_id,
                            action=action, details=details))

def _add_notification(user_id, title, message, notif_type='INFO', app_id=None):
    db.session.add(Notification(user_id=user_id, title=title, message=message,
                                type=notif_type, related_application_id=app_id))

def _update_status(application, new_status, user_id, notes=''):
    if not application.can_transition_to(new_status):
        import logging
        logging.getLogger(__name__).warning(
            'State machine: %s -> %s not in VALID_TRANSITIONS. App: %s',
            application.status, new_status, application.id)
    application.transition_to(new_status)
    db.session.add(ApplicationStatusHistory(
        application_id=application.id, status=new_status,
        changed_by_id=user_id, notes=notes))
    _add_audit(application.id, user_id, f'STATUS_CHANGED_TO_{new_status}', notes)

def _officer(user):
    """Return the Officer profile for an OFFICER user, else None."""
    if user.role != 'OFFICER':
        return None
    return Officer.query.filter_by(user_id=user.id).first()

def _assigned_application_or_403(user, app_id):
    """Owner check: only the assigned officer may access an application."""
    app = Application.query.get_or_404(app_id)
    assignment = ApplicationAssignment.query.filter_by(
        application_id=app.id, status='ACTIVE').first()
    if not assignment or assignment.officer_id != user.id:
        return None, {'error': 'This application is not assigned to your desk.'}, 403
    return app, None, None

def _actionable_application_or_error(app):
    if app.status in TERMINAL:
        return {'error': f'Application is already {app.status.lower()}.'}, 400
    if app.status not in ACTIONABLE:
        return {'error': f'Application is in status {app.status} and cannot be decided yet.'}, 400
    return None, None

def _publish_app_update(app, extra=None):
    """Push a live event to the applicant and whole broker (title updates the
    notification bell and any open page references the same DB state)."""
    payload = {'application_id': app.id,
               'application_number': app.application_number,
               'status': app.status}
    if extra:
        payload.update(extra)
    publish([app.applicant_id, app.assigned_officer_id],
            event='application_update', payload=payload)


def _current_officer_or_403(user):
    profile = _officer(user)
    if profile is None:
        return None
    return profile


@officer_bp.route('/me', methods=['GET'])
@jwt_required()
def officer_me():
    user = get_current_user()
    profile = _current_officer_or_403(user)
    if not profile:
        return jsonify({'error': 'Officer access required'}), 403
    return jsonify({'officer': profile.to_dict()}), 200


@officer_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def officer_dashboard():
    user = get_current_user()
    profile = _current_officer_or_403(user)
    if not profile:
        return jsonify({'error': 'Officer access required'}), 403

    assignments = ApplicationAssignment.query.filter_by(
        officer_id=user.id, status='ACTIVE').all()
    app_ids = [a.application_id for a in assignments]
    apps = Application.query.filter(Application.id.in_(app_ids)).all() if app_ids else []

    by_status = {}
    actionable = []
    awaiting_docs = 0
    under_inspection = 0
    sla_breached = []
    approaching_sla = []
    for a in apps:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        if a.status in ACTIONABLE:
            actionable.append(a)
        if a.status == 'ADDITIONAL_DOCUMENTS_REQUIRED' or a.status == 'CORRECTION_REQUIRED':
            awaiting_docs += 1
        if a.status in INSPECTION_STATES:
            under_inspection += 1
        if a.sla_deadline and a.status not in TERMINAL:
            deadline = (a.sla_deadline.replace(tzinfo=timezone.utc)
                        if a.sla_deadline.tzinfo is None else a.sla_deadline)
            remaining = (deadline - now()).days
            d = a.to_dict()
            if remaining < 0:
                sla_breached.append(d)
            elif remaining <= 3:
                approaching_sla.append(d)

    licence_stats = []
    for ol in profile.licence_types:
        at = ol.approval_type
        if not at:
            continue
        pending = sum(1 for a in apps if a.approval_type_id == at.id and a.status not in TERMINAL)
        active = sum(1 for a in apps if a.approval_type_id == at.id and a.status not in TERMINAL + ('DRAFT',))
        licence_stats.append({
            'code': at.code, 'name': at.name, 'pending': pending, 'active': active,
            'requires_inspection': at.requires_inspection,
        })

    return jsonify({
        'officer': profile.to_dict(),
        'stats': {
            'total_assigned': len(apps),
            'actionable': len(actionable),
            'awaiting_documents': awaiting_docs,
            'under_inspection': under_inspection,
            'approved': by_status.get('APPROVED', 0),
            'rejected': by_status.get('REJECTED', 0),
            'sla_breached': len(sla_breached),
            'approaching_sla': len(approaching_sla),
            'by_status': by_status,
            'pending': sum(1 for a in apps if a.status not in TERMINAL),
            'ai_verified': sum(1 for a in apps if a.ai_reviewed_at),
            'inspection_required': by_status.get('INSPECTION_REQUIRED', 0),
            'inspection_scheduled': by_status.get('INSPECTION_SCHEDULED', 0)
                + by_status.get('INSPECTION_STARTED', 0),
            'reports_pending': by_status.get('INSPECTION_COMPLETED', 0)
                + by_status.get('INSPECTION_PASSED', 0),
            'completed': by_status.get('APPROVED', 0),
        },
        'licences': licence_stats,
        'actionable_applications': [a.to_dict() for a in sorted(actionable, key=lambda x: x.sla_deadline or now())],
        'sla_violations': sla_breached,
        'approaching_sla': approaching_sla,
    }), 200


@officer_bp.route('/applications', methods=['GET'])
@jwt_required()
def officer_applications():
    user = get_current_user()
    profile = _current_officer_or_403(user)
    if not profile:
        return jsonify({'error': 'Officer access required'}), 403

    status = request.args.get('status')
    licence = request.args.get('licence')
    search = (request.args.get('search') or '').strip().lower()
    limit = min(int(request.args.get('limit', 100)), 500)

    q = (Application.query
         .join(ApplicationAssignment, ApplicationAssignment.application_id == Application.id)
         .filter(ApplicationAssignment.officer_id == user.id,
                 ApplicationAssignment.status == 'ACTIVE'))
    if status:
        statuses = [s.strip().upper() for s in status.split(',') if s.strip()]
        if statuses:
            q = q.filter(Application.status.in_(statuses))
    if licence:
        q = q.join(Application.approval_type).filter(
            Application.approval_type.has(code=licence.upper()))
    apps = q.order_by(Application.sla_deadline.asc()).limit(limit).all()
    if search:
        apps = [a for a in apps
                if search in (a.application_number or '').lower()
                or search in (a.business.name or '').lower()
                or search in ((a.applicant.name or '') if a.applicant else '').lower()]

    return jsonify({'applications': [a.to_dict() for a in apps]}), 200


@officer_bp.route('/applications/<app_id>', methods=['GET'])
@jwt_required()
def officer_application_detail(app_id):
    user = get_current_user()
    if not _current_officer_or_403(user):
        return jsonify({'error': 'Officer access required'}), 403
    app, err, code = _assigned_application_or_403(user, app_id)
    if err:
        return jsonify(err), code

    data = app.to_dict(include_details=True)
    inspection = Inspection.query.filter_by(application_id=app.id) \
        .order_by(Inspection.created_at.desc()).first()
    active_inspection = bool(inspection and inspection.status in
                             ('ASSIGNED', 'SCHEDULED', 'STARTED'))
    data['officer_actions'] = {
        'can_decide': app.status in ACTIONABLE and app.status not in TERMINAL,
        'can_pass_inspection': (app.status == 'INSPECTION_COMPLETED'
                                and bool(inspection and inspection.status == 'COMPLETED'
                                         and inspection.overall_result == 'PASS')),
        'can_require_inspection': (app.status == 'DECISION_PENDING'
                                   and app.approval_type
                                   and app.approval_type.requires_inspection
                                   and not active_inspection),
        'can_request_documents': app.status in ACTIONABLE and app.status not in TERMINAL,
        'inspection_required': bool(app.approval_type and app.approval_type.requires_inspection),
        'inspection_passed': bool(inspection and inspection.status == 'COMPLETED'
                                  and inspection.overall_result == 'PASS'),
        'ai_reviewed': app.ai_reviewed_at is not None,
    }
    return jsonify({'application': data}), 200


@officer_bp.route('/applications/<app_id>/approve', methods=['POST'])
@jwt_required()
def officer_approve(app_id):
    user = get_current_user()
    if not _current_officer_or_403(user):
        return jsonify({'error': 'Officer access required'}), 403
    app, err, code = _assigned_application_or_403(user, app_id)
    if err:
        return jsonify(err), code

    data = request.get_json(silent=True) or {}
    reason = (data.get('reason') or '').strip()
    if not reason:
        return jsonify({'error': 'Approval reason is required'}), 400
    err, code = _actionable_application_or_error(app)
    if err:
        return jsonify(err), code

    # Accountable gate: an AI/verification pass must exist before officer sign-off.
    if app.ai_reviewed_at is None:
        return jsonify({'error': 'Automatic verification has not completed for this application yet.'}), 400
    approval_type = app.approval_type
    if approval_type and approval_type.requires_inspection:
        latest = Inspection.query.filter_by(application_id=app.id) \
            .order_by(Inspection.created_at.desc()).first()
        if not latest or latest.status != 'COMPLETED' or latest.overall_result != 'PASS':
            return jsonify({'error': 'This licence requires a completed physical inspection with a PASS result before approval.'}), 400

    _update_status(app, 'APPROVED', user.id, f'Approved by Officer {user.name}. Reason: {reason}')
    app.decision_date = now()

    assignment = ApplicationAssignment.query.filter_by(application_id=app.id).first()
    if assignment:
        assignment.decision = 'APPROVED'
        assignment.decision_notes = reason
        assignment.decided_at = now()

    existing_cert = Certificate.query.filter_by(application_id=app.id).first()
    if not existing_cert:
        biz = Business.query.get(app.business_id)
        at = app.approval_type
        dept = app.department
        cert = Certificate(
            id=gen_id(), application_id=app.id,
            certificate_number=f'NIR-{now().year}-{uuid.uuid4().hex[:6].upper()}',
            business_name=biz.name if biz else '',
            applicant_name=biz.owner_name if biz else '',
            approval_type_name=at.name if at else '',
            department_name=dept.name if dept else '',
            issue_date=now(), valid_until=now() + timedelta(days=365),
            verification_id=f'VID-{uuid.uuid4().hex[:10].upper()}',
            qr_data='DEMO — NIRMAN Unified Platform', is_prototype=True,
        )
        db.session.add(cert)
        db.session.flush()
        db.session.add(Renewal(certificate_id=cert.id, application_id=app.id,
                               expiry_date=cert.valid_until, status='ACTIVE'))
        existing_cert = cert

    _add_audit(app.id, user.id, 'APPLICATION_APPROVED',
               f'Approved by Officer {user.name} ({user.email}). Reason: {reason}')
    _add_notification(app.applicant_id, 'Licence Approved',
                      f'Your application {app.application_number} was approved by the licensing officer. Your certificate is ready.',
                      'SUCCESS', app.id)
    db.session.commit()
    _publish_app_update(app)
    return jsonify({'application': app.to_dict(),
                    'certificate': existing_cert.to_dict() if existing_cert else None}), 200


@officer_bp.route('/applications/<app_id>/reject', methods=['POST'])
@jwt_required()
def officer_reject(app_id):
    user = get_current_user()
    if not _current_officer_or_403(user):
        return jsonify({'error': 'Officer access required'}), 403
    app, err, code = _assigned_application_or_403(user, app_id)
    if err:
        return jsonify(err), code

    data = request.get_json(silent=True) or {}
    reason = (data.get('reason') or '').strip()
    if not reason:
        return jsonify({'error': 'Rejection reason is required'}), 400
    err, code = _actionable_application_or_error(app)
    if err:
        return jsonify(err), code
    if app.ai_reviewed_at is None:
        return jsonify({'error': 'Automatic verification has not completed for this application yet.'}), 400

    _update_status(app, 'REJECTED', user.id, f'Rejected by Officer {user.name}. Reason: {reason}')
    app.decision_date = now()
    app.rejection_reason = reason
    assignment = ApplicationAssignment.query.filter_by(application_id=app.id).first()
    if assignment:
        assignment.decision = 'REJECTED'
        assignment.decision_notes = reason
        assignment.decided_at = now()

    _add_audit(app.id, user.id, 'APPLICATION_REJECTED',
               f'Rejected by Officer {user.name} ({user.email}). Reason: {reason}')
    _add_notification(app.applicant_id, 'Application Rejected',
                      f'Your application {app.application_number} was rejected by the licensing officer. Reason: {reason}',
                      'ERROR', app.id)
    db.session.commit()
    _publish_app_update(app)
    return jsonify({'application': app.to_dict()}), 200


@officer_bp.route('/applications/<app_id>/request-documents', methods=['POST'])
@jwt_required()
def officer_request_documents(app_id):
    user = get_current_user()
    if not _current_officer_or_403(user):
        return jsonify({'error': 'Officer access required'}), 403
    app, err, code = _assigned_application_or_403(user, app_id)
    if err:
        return jsonify(err), code

    data = request.get_json(silent=True) or {}
    notes = (data.get('notes') or '')
    document_list = data.get('documents') or []
    if not notes.strip() and not document_list:
        return jsonify({'error': 'Please provide the additional documents being requested.'}), 400

    # An officer may request a correction while reviewing, not only on
    # decision-pending applications.
    if app.status in TERMINAL:
        return jsonify({'error': f'Application is already {app.status.lower()}.'}), 400
    if app.status not in ('DECISION_PENDING', 'UNDER_REVIEW', 'SUBMITTED',
                          'INSPECTION_COMPLETED', 'INSPECTION_PASSED'):
        return jsonify({'error': f'Application is in status {app.status} and cannot have corrections requested.'}), 400

    app.correction_notes = notes.strip()
    _update_status(app, 'ADDITIONAL_DOCUMENTS_REQUIRED', user.id,
                   f'Officer {user.name} requested additional documents: {notes.strip() or ", ".join(document_list)}')
    assignment = ApplicationAssignment.query.filter_by(application_id=app.id).first()
    if assignment:
        assignment.decision = 'ADDITIONAL_DOCUMENTS'
        assignment.decision_notes = notes.strip() or ', '.join(document_list)
        assignment.decided_at = now()

    _add_audit(app.id, user.id, 'ADDITIONAL_DOCUMENTS_REQUESTED',
               f'Officer {user.name} requested: {notes.strip() or ", ".join(document_list)}')
    _add_notification(app.applicant_id, 'Additional documents requested',
                      f'Officer {user.name} requested more documents for {app.application_number}: {notes.strip() or ", ".join(document_list)}. Please upload them to resume processing.',
                      'WARNING', app.id)
    db.session.commit()
    _publish_app_update(app)
    return jsonify({'application': app.to_dict()}), 200


@officer_bp.route('/applications/<app_id>/require-inspection', methods=['POST'])
@jwt_required()
def officer_require_inspection(app_id):
    user = get_current_user()
    if not _current_officer_or_403(user):
        return jsonify({'error': 'Officer access required'}), 403
    app, err, code = _assigned_application_or_403(user, app_id)
    if err:
        return jsonify(err), code

    approval_type = app.approval_type
    if not approval_type or not approval_type.requires_inspection:
        return jsonify({'error': 'This licence type does not require a physical inspection.'}), 400
    if app.status not in ('DECISION_PENDING', 'SUBMITTED', 'UNDER_REVIEW'):
        return jsonify({'error': f'Cannot request an inspection while the application is in status {app.status}.'}), 400

    existing = Inspection.query.filter_by(application_id=app.id).first()
    if existing and existing.status not in ('COMPLETED', 'CANCELLED'):
        return jsonify({'error': 'An inspection is already scheduled for this application.'}), 400
    if existing and existing.status == 'COMPLETED' and existing.overall_result == 'PASS':
        return jsonify({'error': 'The physical inspection already passed; you can proceed to a decision.'}), 400

    # COMBINED ROLE: the officer who requires inspection also conducts it.
    # The officer themselves owns the inspection, carrying the full
    # review -> schedule -> inspect -> report -> decide workflow in one desk.
    inspector = user

    if existing:
        existing.status = 'ASSIGNED'
        existing.inspector_id = inspector.id if inspector else None
        existing.completed_date = None
        existing.overall_result = None
        existing.recommendation = None
        inspection = existing
    else:
        inspection = Inspection(
            id=gen_id(), application_id=app.id,
            inspector_id=inspector.id if inspector else None,
            assigned_by_id=user.id, status='ASSIGNED',
        )
        db.session.add(inspection)

    _update_status(app, 'INSPECTION_REQUIRED', user.id,
                   f'Officer {user.name} marked this application for physical inspection.')
    assignment = ApplicationAssignment.query.filter_by(application_id=app.id).first()
    if assignment:
        assignment.decision = 'INSPECTION_REQUIRED'
        assignment.decision_notes = 'Physical inspection required before decision.'
        assignment.decided_at = now()

    if inspector:
        _add_notification(inspector.id, 'Inspection assigned',
                          f'You require a physical inspection for {app.application_number}. Complete the inspection to proceed.',
                          'INFO', app.id)
    _add_notification(app.applicant_id, 'Inspection required',
                      'The licensing officer has marked your application for a physical inspection.',
                      'INFO', app.id)
    db.session.commit()
    _publish_app_update(app)
    return jsonify({'application': app.to_dict(include_details=True),
                    'inspection': inspection.to_dict()}), 200


@officer_bp.route('/applications/<app_id>/pass-inspection', methods=['POST'])
@jwt_required()
def officer_pass_inspection(app_id):
    """Officer confirms the completed inspection as passed.

    Transitions the application from INSPECTION_COMPLETED to INSPECTION_PASSED,
    after which the officer may proceed to final approval.
    """
    user = get_current_user()
    if not _current_officer_or_403(user):
        return jsonify({'error': 'Officer access required'}), 403
    app, err, code = _assigned_application_or_403(user, app_id)
    if err:
        return jsonify(err), code

    if app.status != 'INSPECTION_COMPLETED':
        return jsonify({'error': f'Application is in status {app.status}. '
                        'Only applications with a completed inspection may be passed.'}), 400

    latest = Inspection.query.filter_by(application_id=app.id) \
        .order_by(Inspection.created_at.desc()).first()
    if not latest or latest.status != 'COMPLETED':
        return jsonify({'error': 'No completed inspection found for this application.'}), 400
    if latest.overall_result != 'PASS':
        return jsonify({'error': f'Inspection result is {latest.overall_result}. '
                        'Only inspections with a PASS result can be confirmed.'}), 400

    data = request.get_json(silent=True) or {}
    notes = (data.get('notes') or '').strip() or f'Inspection confirmed by Officer {user.name}'

    _update_status(app, 'INSPECTION_PASSED', user.id, notes)
    app.decision_date = now()

    _add_notification(app.applicant_id, 'Inspection confirmed',
                      f'Inspection for application {app.application_number} has been confirmed by the officer.',
                      'SUCCESS', app.id)
    db.session.commit()
    _publish_app_update(app)
    return jsonify({'application': app.to_dict(include_details=True)}), 200
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models import Application, ApplicationStatusHistory, Document, DocumentRequirement, AuditLog, Notification, Inspection, Certificate, Renewal, User, Business, ApprovalType, Department, BusinessLicenceAssignment
from ..services.routing import assign_officer
from ..services.approval_engine import generate_approval_checklist
from ..services.realtime import publish
from ..services import ai_decision_service
from datetime import datetime, timezone, timedelta
import uuid

applications_bp = Blueprint('applications', __name__)

def now():
    return datetime.now(timezone.utc)

def get_current_user():
    """Delegate to the shared 401-safe helper (no silent None)."""
    from .utils import get_current_user as _shared
    return _shared()

def gen_app_number():
    import random
    return f"NIR-{datetime.now().year}-{random.randint(10000, 99999)}"

def add_audit(application_id, user_id, action, details=''):
    log = AuditLog(application_id=application_id, user_id=user_id, action=action, details=details)
    db.session.add(log)

def add_notification(user_id, title, message, notif_type='INFO', app_id=None):
    n = Notification(user_id=user_id, title=title, message=message, type=notif_type, related_application_id=app_id)
    db.session.add(n)

def update_status(application, new_status, user_id, notes=''):
    if not application.can_transition_to(new_status):
        import logging
        logging.getLogger(__name__).warning(
            'State machine: %s -> %s not in VALID_TRANSITIONS, forcing. App: %s',
            application.status, new_status, application.id)
    application.transition_to(new_status)
    history = ApplicationStatusHistory(
        application_id=application.id,
        status=new_status,
        changed_by_id=user_id,
        notes=notes
    )
    db.session.add(history)
    add_audit(application.id, user_id, f'STATUS_CHANGED_TO_{new_status}', notes)

@applications_bp.route('/', methods=['GET'])
@jwt_required()
def get_applications():
    user = get_current_user()
    if user.role == 'APPLICANT':
        apps = Application.query.filter_by(applicant_id=user.id).all()
    elif user.role in ['ADMIN', 'AI_AGENT']:
        apps = Application.query.all()
    else:
        apps = []
    
    return jsonify({'applications': [a.to_dict() for a in apps]}), 200

@applications_bp.route('/<app_id>', methods=['GET'])
@jwt_required()
def get_application(app_id):
    user = get_current_user()
    app = Application.query.get_or_404(app_id)
    
    # Authorization check
    if user.role == 'APPLICANT' and app.applicant_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify({'application': app.to_dict(include_details=True)}), 200

@applications_bp.route('/', methods=['POST'])
@jwt_required()
def create_application():
    user = get_current_user()
    if user.role not in ['APPLICANT', 'ADMIN']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    business_id = data.get('business_id')
    approval_type_id = data.get('approval_type_id')
    
    if not business_id or not approval_type_id:
        return jsonify({'error': 'business_id and approval_type_id required'}), 400
    
    business = Business.query.get(business_id)
    if not business:
        return jsonify({'error': 'Business not found'}), 404
    if user.role == 'APPLICANT' and business.owner_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    approval_type = ApprovalType.query.get(approval_type_id)
    if not approval_type:
        return jsonify({'error': 'Approval type not found'}), 404

    # SERVER-SIDE licence gating: an application may ONLY be created for a
    # licence that was assigned to this business from its sector/operations
    # (persisted by businesses.py from the rule engine). This closes the
    # "apply for any random licence" hole.
    assigned_types = generate_approval_checklist(business)
    if approval_type_id not in {item['approval_type']['id'] for item in assigned_types}:
        applicable = ', '.join(item['approval_type']['name'] for item in assigned_types[:6])
        return jsonify({'error': (
            f'{approval_type.name} is not required for your {business.sector} business '
            f'based on its stated operations and sector. Applicable licences: {applicable}.'
        )}), 400

    # Check duplicate
    existing = Application.query.filter_by(
        business_id=business_id,
        approval_type_id=approval_type_id
    ).filter(Application.status.notin_(['REJECTED', 'EXPIRED'])).first()
    if existing:
        return jsonify({'error': 'Application already exists for this approval', 'application': existing.to_dict()}), 409
    
    app_num = gen_app_number()
    while Application.query.filter_by(application_number=app_num).first():
        app_num = gen_app_number()
    
    application = Application(
        application_number=app_num,
        business_id=business_id,
        approval_type_id=approval_type_id,
        department_id=approval_type.department_id,
        applicant_id=user.id,
        status='DRAFT'
    )
    db.session.add(application)
    db.session.flush()
    
    # The application is created directly in DRAFT. Record the creation in the
    # status history without attempting an (invalid) DRAFT -> DRAFT transition.
    db.session.add(ApplicationStatusHistory(
        application_id=application.id, status='DRAFT', changed_by_id=user.id,
        notes='Application created',
    ))
    add_audit(application.id, user.id, 'APPLICATION_CREATED', f'Application {app_num} created for {approval_type.name}')
    
    db.session.commit()
    return jsonify({'application': application.to_dict(include_details=True)}), 201

@applications_bp.route('/<app_id>/submit', methods=['POST'])
@jwt_required()
def submit_application(app_id):
    user = get_current_user()
    application = Application.query.get_or_404(app_id)
    
    if user.role == 'APPLICANT' and application.applicant_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if application.status not in ['DRAFT', 'CORRECTION_REQUIRED']:
        return jsonify({'error': f'Cannot submit application in {application.status} status'}), 400
    
    # Validate required documents
    approval_type = application.approval_type
    required_docs = DocumentRequirement.query.filter_by(
        approval_type_id=approval_type.id, is_mandatory=True
    ).all()
    
    uploaded_req_ids = {d.requirement_id for d in application.documents if d.requirement_id}
    missing = [r for r in required_docs if r.id not in uploaded_req_ids]
    
    if missing and not data_has_override(request):
        # Allow submit with warning for demo
        pass
    
    application.submission_date = now()
    sla_days = approval_type.sla_days or 15
    application.sla_deadline = now() + timedelta(days=sla_days)
    
    # Route to the AI Compliance Agent (demo: set status; decision engine reviews).
    new_status = 'SUBMITTED'
    update_status(application, new_status, user.id, 'Application submitted by applicant')

    add_audit(application.id, user.id, 'APPLICATION_SUBMITTED',
              f'Application {application.application_number} submitted')

    # Notify applicant
    add_notification(user.id, 'Application Submitted',
                    f'Your application {application.application_number} for {approval_type.name} has been submitted successfully.',
                    'SUCCESS', application.id)

    # Notify the AI Compliance Agent so it can begin its review checks.
    ai_agent = User.query.filter_by(email='ai-agent@system.demo').first()
    if ai_agent:
        add_notification(ai_agent.id, 'New Application',
                        f'Application {application.application_number} queued for AI compliance review.', 'INFO', application.id)

    # Auto-route to the accountable licensing officer (DB-driven, persisted).
    officer = assign_officer(application, actor=user, auto_routed=True)
    if officer:
        add_audit(application.id, user.id, 'OFFICER_ASSIGNED',
                  f'Application auto-routed to Officer {officer.user.name} ({officer.user.email}).')

    # Run the shared AI compliance review immediately on first submit (not just
    # on resubmit). With a verified document set this advances the application
    # to DECISION_PENDING (or INSPECTION_REQUIRED for inspection-gated licences)
    # so it appears in the officer's actionable queue automatically — otherwise
    # it would sit at SUBMITTED and never reach the officer dashboard.
    db.session.commit()
    ai_decision_service.review_and_advance(application, user, enrich=False)
    db.session.commit()
    publish([application.applicant_id], 'application_update',
            {'application_id': application.id,
             'application_number': application.application_number,
             'status': application.status})
    if officer:
        publish([officer.user_id], 'new_assignment',
                {'application_id': application.id,
                 'application_number': application.application_number,
                 'business': application.business.name if application.business else ''})
    return jsonify({'application': application.to_dict(include_details=True)}), 200

@applications_bp.route('/<app_id>/resubmit', methods=['POST'])
@jwt_required()
def resubmit_application(app_id):
    """Resubmit after an officer requested additional documents.

    Sets the application back into automated review; once every required
    document verifies, the shared AI engine advances it to the officer's
    actionable queue again.
    """
    user = get_current_user()
    application = Application.query.get_or_404(app_id)
    if user.role == 'APPLICANT' and application.applicant_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    if application.status not in ['ADDITIONAL_DOCUMENTS_REQUIRED', 'CORRECTION_REQUIRED', 'DOCUMENT_VALIDATION']:
        return jsonify({'error': f'Cannot resubmit an application in {application.status} status'}), 400

    update_status(application, 'SUBMITTED', user.id, 'Re-submitted after additional documents were provided')
    application.correction_notes = None
    add_audit(application.id, user.id, 'APPLICATION_RESUBMITTED',
              'Applicant resubmitted after providing the requested documents')

    # Route to the AI Compliance Agent for a fresh review pass.
    ai_agent = User.query.filter_by(email='ai-agent@system.demo').first()
    add_notification(user.id, 'Application Resubmitted',
                     f'Your application {application.application_number} has been resubmitted for review.',
                     'SUCCESS', application.id)
    if ai_agent:
        add_notification(ai_agent.id, 'Application resubmitted',
                         f'Application {application.application_number} resubmitted for a fresh compliance review.', 'INFO', application.id)

    # Assign an accountable officer (re-routes deterministically if the
    # workload balance changed) and run the engine's review pass.
    officer = assign_officer(application, actor=user, auto_routed=True)
    db.session.commit()
    ai_decision_service.review_and_advance(application, user, enrich=False)
    db.session.commit()

    publish([application.applicant_id], 'application_update',
            {'application_id': application.id,
             'application_number': application.application_number,
             'status': application.status})
    if officer:
        publish([officer.user_id], 'new_assignment',
                {'application_id': application.id,
                 'application_number': application.application_number,
                 'business': application.business.name if application.business else ''})
    return jsonify({'application': application.to_dict(include_details=True)}), 200

def data_has_override(req):
    try:
        d = req.get_json()
        return d and d.get('force_submit', False)
    except:
        return False

@applications_bp.route('/<app_id>/correction', methods=['POST'])
@jwt_required()
def submit_correction(app_id):
    user = get_current_user()
    application = Application.query.get_or_404(app_id)
    
    if user.role == 'APPLICANT' and application.applicant_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if application.status != 'CORRECTION_REQUIRED':
        return jsonify({'error': 'No correction required'}), 400
    
    data = request.get_json()
    notes = data.get('notes', 'Correction submitted by applicant')
    
    update_status(application, 'SUBMITTED', user.id, notes)
    add_audit(application.id, user.id, 'CORRECTION_SUBMITTED', notes)
    add_notification(user.id, 'Correction Submitted',
                    f'Your correction for {application.application_number} has been submitted.', 'SUCCESS', application.id)
    
    db.session.commit()
    return jsonify({'application': application.to_dict(include_details=True)}), 200

@applications_bp.route('/<app_id>/withdraw', methods=['POST'])
@jwt_required()
def withdraw_application(app_id):
    user = get_current_user()
    application = Application.query.get_or_404(app_id)
    
    if user.role == 'APPLICANT' and application.applicant_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if application.status not in ['DRAFT', 'SUBMITTED']:
        return jsonify({'error': 'Cannot withdraw application in current status'}), 400
    
    update_status(application, 'REJECTED', user.id, 'Withdrawn by applicant')
    application.rejection_reason = 'Withdrawn by applicant'
    add_audit(application.id, user.id, 'APPLICATION_WITHDRAWN', 'Applicant withdrew application')
    db.session.commit()
    return jsonify({'message': 'Application withdrawn'}), 200


@applications_bp.route('/<app_id>', methods=['DELETE'])
@jwt_required()
def delete_draft_application(app_id):
    """Remove only a draft/correction application; finalized records stay auditable."""
    user = get_current_user()
    application = Application.query.get_or_404(app_id)
    if user.role == 'APPLICANT' and application.applicant_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    if user.role not in ['APPLICANT', 'ADMIN']:
        return jsonify({'error': 'Unauthorized'}), 403
    if application.status not in ['DRAFT', 'CORRECTION_REQUIRED']:
        return jsonify({'error': 'Finalized or in-progress applications are retained as an audit record and cannot be deleted.'}), 400

    # Child rows have no database-level cascade in this prototype, so remove
    # only draft-associated operational data before the application itself.
    for document in list(application.documents):
        try:
            import os
            if document.file_path and os.path.exists(document.file_path):
                os.remove(document.file_path)
        except OSError:
            pass
        db.session.delete(document)
    for inspection in list(application.inspections):
        db.session.delete(inspection)
    for history in list(application.status_history):
        db.session.delete(history)
    for log in list(application.audit_logs):
        db.session.delete(log)
    db.session.delete(application)
    db.session.commit()
    return jsonify({'message': 'Draft application deleted.'}), 200

@applications_bp.route('/business/<business_id>', methods=['GET'])
@jwt_required()
def get_business_applications(business_id):
    user = get_current_user()
    business = Business.query.get_or_404(business_id)
    
    if user.role == 'APPLICANT' and business.owner_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    apps = Application.query.filter_by(business_id=business_id).all()
    return jsonify({'applications': [a.to_dict() for a in apps]}), 200

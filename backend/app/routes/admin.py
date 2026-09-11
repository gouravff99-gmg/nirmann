from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models import Application, User, AuditLog, Notification, Certificate, Inspection, Business, Department, Renewal, ApplicationStatusHistory, gen_id
from ..services.realtime import publish
from datetime import datetime, timezone, timedelta
from sqlalchemy import func
import uuid

admin_bp = Blueprint('admin', __name__)

def _add_audit(application_id, user_id, action, details=''):
    log = AuditLog(application_id=application_id, user_id=user_id, action=action, details=details)
    db.session.add(log)

def _add_notification(user_id, title, message, notif_type='INFO', app_id=None):
    n = Notification(user_id=user_id, title=title, message=message, type=notif_type, related_application_id=app_id)
    db.session.add(n)

def _update_status(application, new_status, user_id, notes=''):
    if not application.can_transition_to(new_status):
        import logging
        logging.getLogger(__name__).warning(
            'State machine: %s -> %s not in VALID_TRANSITIONS. App: %s',
            application.status, new_status, application.id)
    application.transition_to(new_status)
    history = ApplicationStatusHistory(
        application_id=application.id, status=new_status, changed_by_id=user_id, notes=notes
    )
    db.session.add(history)
    _add_audit(application.id, user_id, f'STATUS_CHANGED_TO_{new_status}', notes)

def get_current_user():
    """Delegate to the shared 401-safe helper (no silent None)."""
    from .utils import get_current_user as _shared
    return _shared()

def require_admin(user):
    return user.role == 'ADMIN'

def now():
    return datetime.now(timezone.utc)

@admin_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def admin_dashboard():
    user = get_current_user()
    if not require_admin(user):
        return jsonify({'error': 'Unauthorized'}), 403
    
    apps = Application.query.all()
    businesses = Business.query.all()
    users = User.query.all()
    inspections = Inspection.query.all()
    certs = Certificate.query.all()
    
    # By status
    status_counts = {}
    for a in apps:
        status_counts[a.status] = status_counts.get(a.status, 0) + 1
    
    # SLA analysis
    sla_breached = []
    approaching_sla = []
    for a in apps:
        if a.sla_deadline and a.status not in ['APPROVED', 'REJECTED', 'EXPIRED']:
            deadline = a.sla_deadline.replace(tzinfo=timezone.utc) if a.sla_deadline.tzinfo is None else a.sla_deadline
            remaining = (deadline - now()).days
            if remaining < 0:
                sla_breached.append(a.to_dict())
            elif remaining <= 3:
                approaching_sla.append(a.to_dict())
    
    # Department stats
    dept_stats = {}
    for a in apps:
        if a.department:
            dept = a.department.name
            if dept not in dept_stats:
                dept_stats[dept] = {'total': 0, 'approved': 0, 'rejected': 0, 'pending': 0}
            dept_stats[dept]['total'] += 1
            if a.status == 'APPROVED':
                dept_stats[dept]['approved'] += 1
            elif a.status == 'REJECTED':
                dept_stats[dept]['rejected'] += 1
            else:
                dept_stats[dept]['pending'] += 1
    
    # By sector
    sector_stats = {}
    for b in businesses:
        sector = b.sector
        sector_stats[sector] = sector_stats.get(sector, 0) + 1
    
    return jsonify({
        'stats': {
            'total_applications': len(apps),
            'total_businesses': len(businesses),
            'total_users': len(users),
            'total_inspections': len(inspections),
            'total_certificates': len(certs),
            'by_status': status_counts,
            'sla_breached': len(sla_breached),
            'approaching_sla': len(approaching_sla),
        },
        'recent_applications': [a.to_dict() for a in sorted(apps, key=lambda x: x.created_at or now(), reverse=True)[:10]],
        'sla_violations': sla_breached,
        'approaching_sla': approaching_sla,
        'department_stats': [{'department': k, **v} for k, v in dept_stats.items()],
        'sector_stats': [{'sector': k, 'count': v} for k, v in sector_stats.items()],
    }), 200

@admin_bp.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    user = get_current_user()
    if not require_admin(user):
        return jsonify({'error': 'Unauthorized'}), 403
    
    users = User.query.all()
    return jsonify({'users': [u.to_dict() for u in users]}), 200

@admin_bp.route('/users/<user_id>/toggle', methods=['POST'])
@jwt_required()
def toggle_user(user_id):
    admin = get_current_user()
    if not require_admin(admin):
        return jsonify({'error': 'Unauthorized'}), 403
    
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({'user': user.to_dict()}), 200

@admin_bp.route('/audit-logs', methods=['GET'])
@jwt_required()
def get_audit_logs():
    user = get_current_user()
    if not require_admin(user):
        return jsonify({'error': 'Unauthorized'}), 403
    
    app_id = request.args.get('application_id')
    limit = int(request.args.get('limit', 100))
    
    query = AuditLog.query
    if app_id:
        query = query.filter_by(application_id=app_id)
    
    logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return jsonify({'audit_logs': [l.to_dict() for l in logs]}), 200

@admin_bp.route('/applications', methods=['GET'])
@jwt_required()
def admin_applications():
    user = get_current_user()
    if not require_admin(user):
        return jsonify({'error': 'Unauthorized'}), 403
    limit = min(int(request.args.get('limit', 200)), 500)
    apps = (Application.query
            .order_by(Application.created_at.desc())
            .limit(limit)
            .all())
    return jsonify({'applications': [a.to_dict() for a in apps]}), 200

@admin_bp.route('/analytics', methods=['GET'])
@jwt_required()
def analytics():
    user = get_current_user()
    if not require_admin(user):
        return jsonify({'error': 'Unauthorized'}), 403
    
    apps = Application.query.all()
    
    # Monthly trend
    monthly = {}
    for a in apps:
        if a.submission_date:
            key = a.submission_date.strftime('%Y-%m')
            monthly[key] = monthly.get(key, 0) + 1
    
    # Approval rate by dept
    dept_approval = {}
    for a in apps:
        dept = a.department.name if a.department else 'Unknown'
        if dept not in dept_approval:
            dept_approval[dept] = {'total': 0, 'approved': 0, 'rejected': 0, 'avg_days': [], 'sla': a.department.sla_days if a.department else 15}
        dept_approval[dept]['total'] += 1
        if a.status == 'APPROVED':
            dept_approval[dept]['approved'] += 1
            if a.submission_date and a.decision_date:
                sub = a.submission_date.replace(tzinfo=timezone.utc) if a.submission_date.tzinfo is None else a.submission_date
                dec = a.decision_date.replace(tzinfo=timezone.utc) if a.decision_date.tzinfo is None else a.decision_date
                days = (dec - sub).days
                dept_approval[dept]['avg_days'].append(days)
        elif a.status == 'REJECTED':
            dept_approval[dept]['rejected'] += 1
    
    for dept in dept_approval:
        days_list = dept_approval[dept].pop('avg_days', [])
        dept_approval[dept]['avg_processing_days'] = round(sum(days_list) / len(days_list), 1) if days_list else 0
    
    return jsonify({
        'monthly_applications': [{'month': k, 'count': v} for k, v in sorted(monthly.items())],
        'department_performance': [{'department': k, **v} for k, v in dept_approval.items()],
    }), 200

@admin_bp.route('/applications/<app_id>/approve', methods=['POST'])
@jwt_required()
def approve_application(app_id):
    admin = get_current_user()
    if not require_admin(admin):
        return jsonify({'error': 'Admin access required'}), 403
    app = Application.query.get_or_404(app_id)
    data = request.get_json(silent=True) or {}
    reason = data.get('reason', '').strip()
    if not reason:
        return jsonify({'error': 'Approval reason is required'}), 400
    if app.status in ['APPROVED', 'REJECTED']:
        return jsonify({'error': f'Application is already {app.status.lower()}'}), 400

    # Accountable decision order: AI compliance review first, then any required
    # physical inspection must have completed with a PASS result.
    if app.ai_reviewed_at is None:
        return jsonify({'error': 'Run the AI compliance review before approving. The AI Agent must assess verification first.'}), 400
    approval_type = app.approval_type
    if approval_type and approval_type.requires_inspection:
        latest = Inspection.query.filter_by(application_id=app.id) \
            .order_by(Inspection.created_at.desc()).first()
        if not latest or latest.status != 'COMPLETED' or latest.overall_result != 'PASS':
            return jsonify({'error': 'This approval requires a physical inspection that must be completed with a PASS result before it can be approved.'}), 400

    _update_status(app, 'APPROVED', admin.id, f'Approved by admin. Reason: {reason}')
    app.decision_date = now()

    existing_cert = Certificate.query.filter_by(application_id=app.id).first()
    if not existing_cert:
        biz = Business.query.get(app.business_id)
        at = app.approval_type
        dept = app.department
        cert = Certificate(
            id=gen_id(), application_id=app.id,
            certificate_number=f'NIRMAN-{datetime.now().year}-{uuid.uuid4().hex[:6].upper()}',
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
        existing_cert = cert
        db.session.add(Renewal(certificate_id=cert.id, application_id=app.id, expiry_date=cert.valid_until, status='ACTIVE'))
    _add_audit(app.id, admin.id, 'APPLICATION_APPROVED', f'Approved. Reason: {reason}')
    _add_notification(app.applicant_id, 'Application Approved', f'Your application {app.application_number} has been approved.', 'SUCCESS', app.id)
    db.session.commit()
    publish([app.applicant_id, app.assigned_officer_id],
            'application_update', {'application_id': app.id,
                                   'application_number': app.application_number,
                                   'status': app.status})
    return jsonify({'application': app.to_dict(), 'certificate': existing_cert.to_dict() if existing_cert else None}), 200


@admin_bp.route('/applications/<app_id>/reject', methods=['POST'])
@jwt_required()
def reject_application(app_id):
    admin = get_current_user()
    if not require_admin(admin):
        return jsonify({'error': 'Admin access required'}), 403
    app = Application.query.get_or_404(app_id)
    data = request.get_json(silent=True) or {}
    reason = data.get('reason', '').strip()
    if not reason:
        return jsonify({'error': 'Rejection reason is required'}), 400
    if app.status in ['APPROVED', 'REJECTED']:
        return jsonify({'error': f'Application is already {app.status.lower()}'}), 400

    if app.ai_reviewed_at is None:
        return jsonify({'error': 'Run the AI compliance review before deciding. The AI Agent must assess verification first.'}), 400

    _update_status(app, 'REJECTED', admin.id, f'Rejected by admin. Reason: {reason}')
    app.decision_date = now()
    app.rejection_reason = reason

    _add_audit(app.id, admin.id, 'APPLICATION_REJECTED', f'Rejected. Reason: {reason}')
    _add_notification(app.applicant_id, 'Application Rejected', f'Your application {app.application_number} has been rejected. Reason: {reason}', 'ERROR', app.id)
    db.session.commit()
    publish([app.applicant_id, app.assigned_officer_id],
            'application_update', {'application_id': app.id,
                                   'application_number': app.application_number,
                                   'status': app.status})
    return jsonify({'application': app.to_dict()}), 200


@admin_bp.route('/demo-reset', methods=['POST'])
@jwt_required()
def demo_reset():
    """Reset demo database to initial seed state."""
    identity = get_jwt_identity()
    user = User.query.get(identity)
    if not user or user.role != 'ADMIN':
        return jsonify({'error': 'Admin access required'}), 403
    
    try:
        import subprocess
        import sys
        import os
        basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        result = subprocess.run(
            [sys.executable, 'seed.py'],
            cwd=basedir,
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return jsonify({'message': 'Demo data reset successfully', 'output': result.stdout}), 200
        else:
            return jsonify({'error': 'Reset failed', 'details': result.stderr}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

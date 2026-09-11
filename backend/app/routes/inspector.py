from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models import Inspection, InspectionEvidence, Application, ApplicationStatusHistory, AuditLog, Notification, User
from ..services.realtime import publish
from datetime import datetime, timezone
import os, uuid
from werkzeug.utils import secure_filename

inspector_bp = Blueprint('inspector', __name__)

def now():
    return datetime.now(timezone.utc)

def get_current_user():
    """Delegate to the shared 401-safe helper (no silent None)."""
    from .utils import get_current_user as _shared
    return _shared()

def add_audit(application_id, user_id, action, details=''):
    log = AuditLog(application_id=application_id, user_id=user_id, action=action, details=details)
    db.session.add(log)

def add_notification(user_id, title, message, notif_type='INFO', app_id=None):
    n = Notification(user_id=user_id, title=title, message=message, type=notif_type, related_application_id=app_id)
    db.session.add(n)

def update_app_status(application, new_status, user_id, notes=''):
    if not application.can_transition_to(new_status):
        import logging
        logging.getLogger(__name__).warning(
            'State machine: %s -> %s not in VALID_TRANSITIONS. App: %s',
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

@inspector_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def inspector_dashboard():
    user = get_current_user()
    if user.role not in ['OFFICER', 'ADMIN']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if user.role == 'ADMIN':
        inspections = Inspection.query.all()
    else:
        inspections = Inspection.query.filter_by(inspector_id=user.id).all()
    
    result = []
    for insp in inspections:
        app = Application.query.get(insp.application_id)
        insp_dict = insp.to_dict()
        if app:
            insp_dict['application'] = app.to_dict()
            insp_dict['business'] = app.business.to_dict() if app.business else None
        result.append(insp_dict)
    
    return jsonify({
        'inspections': result,
        'stats': {
            'total': len(inspections),
            'pending': sum(1 for i in inspections if i.status == 'PENDING'),
            'assigned': sum(1 for i in inspections if i.status == 'ASSIGNED'),
            'scheduled': sum(1 for i in inspections if i.status == 'SCHEDULED'),
            'completed': sum(1 for i in inspections if i.status == 'COMPLETED'),
        }
    }), 200

@inspector_bp.route('/<inspection_id>/accept', methods=['POST'])
@jwt_required()
def accept_inspection(inspection_id):
    user = get_current_user()
    if user.role not in ['OFFICER', 'ADMIN']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    inspection = Inspection.query.get_or_404(inspection_id)
    if inspection.inspector_id and inspection.inspector_id != user.id and user.role != 'ADMIN':
        return jsonify({'error': 'Not your inspection'}), 403
    
    inspection.inspector_id = user.id
    inspection.status = 'ASSIGNED'
    
    add_audit(inspection.application_id, user.id, 'INSPECTION_ACCEPTED', f'Accepted by inspector {user.name}')
    db.session.commit()
    application = Application.query.get(inspection.application_id)
    if application:
        publish([application.applicant_id, application.assigned_officer_id],
                'application_update', {'application_id': application.id,
                                       'application_number': application.application_number,
                                       'status': application.status})
    return jsonify({'inspection': inspection.to_dict()}), 200

@inspector_bp.route('/<inspection_id>/schedule', methods=['POST'])
@jwt_required()
def schedule_inspection(inspection_id):
    user = get_current_user()
    if user.role not in ['OFFICER', 'ADMIN']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    inspection = Inspection.query.get_or_404(inspection_id)
    if user.role == 'OFFICER' and inspection.inspector_id and inspection.inspector_id != user.id:
        return jsonify({'error': 'Not your inspection'}), 403
    data = request.get_json()
    scheduled_date_str = data.get('scheduled_date')
    
    if not scheduled_date_str:
        return jsonify({'error': 'scheduled_date is required'}), 400
    
    try:
        scheduled_date = datetime.fromisoformat(scheduled_date_str.replace('Z', '+00:00'))
    except:
        return jsonify({'error': 'Invalid date format. Use ISO 8601.'}), 400
    
    inspection.scheduled_date = scheduled_date
    inspection.status = 'SCHEDULED'
    
    application = Application.query.get(inspection.application_id)
    if application:
        update_app_status(application, 'INSPECTION_SCHEDULED', user.id, f'Inspection scheduled for {scheduled_date_str}')
        add_notification(application.applicant_id, 'Inspection Scheduled',
                        f'Inspection for your application {application.application_number} is scheduled for {scheduled_date.strftime("%d %b %Y")}.',
                        'INFO', application.id)
    
    add_audit(inspection.application_id, user.id, 'INSPECTION_SCHEDULED', f'Scheduled for {scheduled_date_str}')
    db.session.commit()
    if application:
        publish([application.applicant_id, application.assigned_officer_id],
                'application_update', {'application_id': application.id,
                                       'application_number': application.application_number,
                                       'status': application.status})
    return jsonify({'inspection': inspection.to_dict()}), 200

@inspector_bp.route('/<inspection_id>/start', methods=['POST'])
@jwt_required()
def start_inspection(inspection_id):
    user = get_current_user()
    if user.role not in ['OFFICER', 'ADMIN']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    inspection = Inspection.query.get_or_404(inspection_id)
    if user.role == 'OFFICER' and inspection.inspector_id and inspection.inspector_id != user.id:
        return jsonify({'error': 'Not your inspection'}), 403
    inspection.status = 'STARTED'
    
    add_audit(inspection.application_id, user.id, 'INSPECTION_STARTED', f'Inspection started by {user.name}')
    db.session.flush()
    application = Application.query.get(inspection.application_id)
    if application:
        if application.status in ('INSPECTION_SCHEDULED', 'IN_PROGRESS'):
            update_app_status(application, 'IN_PROGRESS', user.id,
                              f'Inspection started by {user.name}')
        db.session.commit()
        publish([application.applicant_id, application.assigned_officer_id],
                'application_update', {'application_id': application.id,
                                       'application_number': application.application_number,
                                       'status': application.status})
    else:
        db.session.commit()
    return jsonify({'inspection': inspection.to_dict()}), 200

@inspector_bp.route('/<inspection_id>/submit-report', methods=['POST'])
@jwt_required()
def submit_inspection_report(inspection_id):
    user = get_current_user()
    if user.role not in ['OFFICER', 'ADMIN']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    inspection = Inspection.query.get_or_404(inspection_id)
    if user.role == 'OFFICER' and inspection.inspector_id and inspection.inspector_id != user.id:
        return jsonify({'error': 'Not your inspection'}), 403
    if inspection.status == 'COMPLETED':
        return jsonify({'error': 'Inspection report has already been submitted for this inspection.'}), 400
    data = request.get_json()

    checklist_data = data.get('checklist_data', '[]')
    remarks = (data.get('remarks') or '').strip()
    recommendation = data.get('recommendation', 'APPROVE')
    overall_result = data.get('overall_result', 'PASS')
    decision_reason = (data.get('decision_reason') or '').strip()

    if isinstance(checklist_data, (list, dict)):
        import json
        checklist_data = json.dumps(checklist_data)

    # Accountable gate: PASS_WITH_CORRECTIONS and FAIL require an explicit
    # reason and remarks — never allow submission without accountability.
    if overall_result in ('PASS_WITH_CORRECTIONS', 'FAIL', 'CONDITIONAL'):
        if not decision_reason:
            return jsonify({'error': 'A reason is required when the inspection result is not a full PASS.'}), 400
        if not remarks:
            return jsonify({'error': 'Remarks are required when the inspection result is not a full PASS.'}), 400

    inspection.checklist_data = checklist_data
    inspection.remarks = remarks
    inspection.recommendation = recommendation
    inspection.overall_result = overall_result
    inspection.decision_reason = decision_reason
    inspection.completed_date = now()
    inspection.report_submitted_at = now()
    inspection.status = 'COMPLETED'
    
    application = Application.query.get(inspection.application_id)
    if application:
        update_app_status(application, 'INSPECTION_COMPLETED', user.id, f'Inspection completed. Result: {overall_result}. Recommendation: {recommendation}')
        add_notification(application.applicant_id, 'Inspection Completed',
                        f'Inspection for application {application.application_number} has been completed. Result: {overall_result}',
                        'SUCCESS' if overall_result == 'PASS' else 'WARNING', application.id)
        # Notify the AI Compliance Agent so it can process the inspection result.
        ai_agent = User.query.filter_by(email='ai-agent@system.demo').first()
        if ai_agent:
            add_notification(ai_agent.id, 'Inspection Report Submitted',
                            f'Inspection report for {application.application_number} is ready for AI review. Recommendation: {recommendation}',
                            'INFO', application.id)
    
    add_audit(inspection.application_id, user.id, 'INSPECTION_REPORT_SUBMITTED',
              f'Inspection completed. Result: {overall_result}. Recommendation: {recommendation}. Decision reason: {decision_reason}')
    db.session.commit()
    if application:
        publish([application.applicant_id, application.assigned_officer_id],
                'application_update', {'application_id': application.id,
                                       'application_number': application.application_number,
                                       'status': application.status})
    return jsonify({'inspection': inspection.to_dict()}), 200

@inspector_bp.route('/<inspection_id>/upload-evidence', methods=['POST'])
@jwt_required()
def upload_evidence(inspection_id):
    user = get_current_user()
    if user.role not in ['OFFICER', 'ADMIN']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    inspection = Inspection.query.get_or_404(inspection_id)
    if user.role == 'OFFICER' and inspection.inspector_id and inspection.inspector_id != user.id:
        return jsonify({'error': 'Not your inspection'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    caption = request.form.get('caption', '')
    
    original_filename = secure_filename(file.filename)
    ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else 'jpg'
    unique_filename = f"evidence_{uuid.uuid4().hex}.{ext}"
    
    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_path = os.path.join(upload_folder, unique_filename)
    file.save(file_path)
    
    evidence = InspectionEvidence(
        inspection_id=inspection_id,
        filename=unique_filename,
        original_filename=original_filename,
        file_path=file_path,
        caption=caption
    )
    db.session.add(evidence)
    
    add_audit(inspection.application_id, user.id, 'EVIDENCE_UPLOADED', f'Evidence uploaded: {original_filename}')
    db.session.commit()
    
    return jsonify({'evidence': evidence.to_dict()}), 201

@inspector_bp.route('/<inspection_id>', methods=['GET'])
@jwt_required()
def get_inspection(inspection_id):
    user = get_current_user()
    inspection = Inspection.query.get_or_404(inspection_id)
    
    if user.role == 'OFFICER' and inspection.inspector_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    app = Application.query.get(inspection.application_id)
    result = inspection.to_dict()
    if app:
        result['application'] = app.to_dict(include_details=True)
        result['business'] = app.business.to_dict() if app.business else None
    
    return jsonify({'inspection': result}), 200

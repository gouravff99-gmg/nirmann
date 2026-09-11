from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models import Business, Application, ApprovalType, ApprovalRule, User, AuditLog, BusinessLicenceAssignment
from ..services.approval_engine import generate_approval_checklist, assign_licences_for_business
import re

businesses_bp = Blueprint('businesses', __name__)

def get_current_user():
    """Delegate to the shared 401-safe helper (no silent None)."""
    from .utils import get_current_user as _shared
    return _shared()


def parse_investment(value):
    """Parse investment amounts leniently, matching the frontend helper.

    Accepts plain numbers, comma-separated Indian notation, a rupee symbol
    and lakh/crore/K/M suffixes (e.g. "1,50,00,000", "₹25 Lakh", "1.5 Crore").
    Returns a float, or 0 when the value cannot be interpreted.
    """
    if value is None:
        return 0
    s = str(value).strip()
    if s == '':
        return 0
    try:
        return float(s)
    except (TypeError, ValueError):
        pass
    cleaned = s.replace(',', '').replace('₹', '').strip().upper()
    match = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)\s*(CRORE|CR|LAKH|L|K|M)?', cleaned)
    if not match:
        try:
            return float(cleaned)
        except (TypeError, ValueError):
            return 0
    amount = float(match.group(1))
    unit = match.group(2)
    multiplier = {
        'CRORE': 10000000, 'CR': 10000000,
        'LAKH': 100000, 'L': 100000,
        'K': 1000, 'M': 1000000,
    }.get(unit, 1)
    return amount * multiplier


def parse_employee_count(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _pending_documents(business):
    """Total documents the applicant still has to apply/submit for a business.

    Every checklist approval that is not yet approved contributes its full set
    of required documents, minus any documents already uploaded for an
    in-progress application. This gives the applicant a single "docs still to
    apply" figure right after registering.
    """
    apps = {a.approval_type_id: a for a in Application.query.filter_by(business_id=business.id).all()}
    total = 0
    for item in generate_approval_checklist(business):
        at = item.get('approval_type') or {}
        app = apps.get(at.get('id'))
        if app and app.status == 'APPROVED':
            continue
        required = len(at.get('document_requirements') or [])
        uploaded = 0
        if app:
            uploaded = sum(1 for d in app.documents
                       if d.status in ('UPLOADED', 'VALIDATION_PENDING', 'UNDER_OFFICER_REVIEW',
                                       'UNDER_REVIEW', 'APPROVED', 'VERIFIED'))
        total += max(required - uploaded, 0)
    return total


def _business_requirements(business):
    """Dynamic per-business required approvals — the single source of truth.

    Reuses the existing rule engine (generate_approval_checklist) so the
    Applicant, Inspector and Admin dashboards all derive counts from the same
    compliance rules. Real application status is joined per approval type, so
    nothing here is hardcoded.
    """
    apps = {a.approval_type_id: a for a in Application.query.filter_by(business_id=business.id).all()}
    requirements = []
    for item in generate_approval_checklist(business):
        at = item.get('approval_type') or {}
        app = apps.get(at.get('id'))
        requirements.append({
            'approval_type_id': at.get('id'),
            'name': at.get('name'),
            'code': at.get('code'),
            'department': (at.get('department') or {}).get('name'),
            'requires_inspection': at.get('requires_inspection', False),
            'estimated_days': at.get('estimated_days'),
            'why_triggered': item.get('why_triggered'),
            'is_mandatory': item.get('is_mandatory'),
            'application_id': app.id if app else None,
            'application_number': app.application_number if app else None,
            'application_status': app.status if app else 'NOT_APPLIED',
        })
    return requirements


def _requirements_counts(requirements):
    """Total / Approved / Pending for a business's required approvals.

    Every consumer (business card, approval progress page, dashboards) derives
    these from the same checklist so approving a single application updates
    every counter automatically. Approved counts status APPROVED on the
    joined application; Pending is simply what remains.
    """
    approved = sum(1 for r in requirements if r.get('application_status') == 'APPROVED')
    return {
        'required_total': len(requirements),
        'required_approved': approved,
        'required_pending': len(requirements) - approved,
    }

@businesses_bp.route('/', methods=['GET'])
@jwt_required()
def get_businesses():
    user = get_current_user()
    if user.role == 'ADMIN':
        businesses = Business.query.all()
    else:
        businesses = Business.query.filter_by(owner_id=user.id).all()
    
    result = []
    for b in businesses:
        b_dict = b.to_dict()
        apps = Application.query.filter_by(business_id=b.id).all()
        b_dict['total_approvals'] = len(apps)
        b_dict['approved'] = sum(1 for a in apps if a.status == 'APPROVED')
        b_dict['pending'] = sum(1 for a in apps if a.status in ['SUBMITTED', 'UNDER_REVIEW', 'INSPECTION_REQUIRED', 'INSPECTION_SCHEDULED', 'INSPECTION_COMPLETED', 'DECISION_PENDING'])
        b_dict['corrections'] = sum(1 for a in apps if a.status == 'CORRECTION_REQUIRED')
        b_dict['inspections'] = sum(1 for a in apps if a.status in ['INSPECTION_REQUIRED', 'INSPECTION_SCHEDULED'])
        b_dict['pending_documents'] = _pending_documents(b)
        requirements = _business_requirements(b)
        b_dict['required_approvals'] = requirements
        b_dict['total_required'] = len(requirements)
        b_dict.update(_requirements_counts(requirements))
        b_dict['licence_assignments'] = _licence_assignments(b.id)
        result.append(b_dict)
    
    return jsonify({'businesses': result}), 200

def _licence_assignments(business_id):
    """Persisted sector→licence assignments for a business (SQLite source of truth)."""
    return [a.to_dict() for a in BusinessLicenceAssignment.query.filter_by(business_id=business_id).all()]

@businesses_bp.route('/<business_id>', methods=['GET'])
@jwt_required()
def get_business(business_id):
    user = get_current_user()
    business = Business.query.get_or_404(business_id)
    
    if user.role == 'APPLICANT' and business.owner_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    b_dict = business.to_dict()
    apps = Application.query.filter_by(business_id=business_id).all()
    b_dict['applications'] = [a.to_dict() for a in apps]
    b_dict['total_approvals'] = len(apps)
    b_dict['approved'] = sum(1 for a in apps if a.status == 'APPROVED')
    b_dict['pending'] = sum(1 for a in apps if a.status in ['SUBMITTED', 'UNDER_REVIEW', 'INSPECTION_REQUIRED', 'INSPECTION_SCHEDULED', 'INSPECTION_COMPLETED', 'DECISION_PENDING'])
    b_dict['corrections'] = sum(1 for a in apps if a.status == 'CORRECTION_REQUIRED')
    b_dict['pending_documents'] = _pending_documents(business)
    requirements = _business_requirements(business)
    b_dict['required_approvals'] = requirements
    b_dict['total_required'] = len(requirements)
    b_dict.update(_requirements_counts(requirements))
    b_dict['licence_assignments'] = _licence_assignments(business_id)
    
    return jsonify({'business': b_dict}), 200

@businesses_bp.route('/', methods=['POST'])
@jwt_required()
def create_business():
    user = get_current_user()
    if user.role not in ['APPLICANT', 'ADMIN']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    required = ['name', 'owner_name', 'business_type', 'sector', 'state']
    for f in required:
        if not data.get(f):
            return jsonify({'error': f'{f} is required'}), 400

    # Prevent duplicate business names per owner
    dup = Business.query.filter_by(owner_id=user.id, name=data['name']).first()
    if dup:
        return jsonify({'error': 'A business named "%s" is already registered by this owner' % data['name']}), 400

    # Limit APPLICANT to 10 registered businesses
    if user.role == 'APPLICANT':
        owner_count = Business.query.filter_by(owner_id=user.id).count()
        if owner_count >= 10:
            return jsonify({'error': 'Maximum of 10 businesses can be registered. Delete an existing business to add a new one.'}), 400
    
    # Determine fire risk based on operations
    fire_risk = 'LOW'
    if data.get('uses_hazardous') or data.get('is_manufacturing'):
        fire_risk = 'HIGH'
    elif data.get('handles_food') or data.get('uses_heavy_machinery'):
        fire_risk = 'MEDIUM'
    
    # Determine size category
    investment = parse_investment(data.get('investment_amount'))
    employees = parse_employee_count(data.get('employee_count'))
    if investment > 10000000 or employees > 250:  # 1 Crore+
        size_category = 'LARGE'
    elif investment > 2500000 or employees > 50:  # 25 Lakh+
        size_category = 'MEDIUM'
    else:
        size_category = 'SMALL'
    
    import uuid
    reg_num = f'BRN-{str(uuid.uuid4())[:8].upper()}'
    
    business = Business(
        owner_id=user.id,
        name=data['name'],
        owner_name=data['owner_name'],
        business_type=data['business_type'],
        sector=data['sector'],
        state=data['state'],
        district=data.get('district', ''),
        city=data.get('city', ''),
        address=data.get('address', ''),
        investment_amount=investment,
        employee_count=employees,
        size_category=size_category,
        is_manufacturing=data.get('is_manufacturing', False),
        handles_food=data.get('handles_food', False),
        involves_construction=data.get('involves_construction', False),
        uses_hazardous=data.get('uses_hazardous', False),
        uses_heavy_machinery=data.get('uses_heavy_machinery', False),
        has_physical_infra=data.get('has_physical_infra', True),
        env_approval_applicable=data.get('env_approval_applicable', False),
        fire_risk=fire_risk,
        registration_number=reg_num
    )
    
    db.session.add(business)
    db.session.commit()
    
    # Generate approval checklist AND persist the derived sector→licence
    # assignment in SQLite (server-side source of truth). The frontend only
    # renders this mapping; create_application enforces it server-side.
    checklist = generate_approval_checklist(business)
    licence_assignments = assign_licences_for_business(business)
    
    log = AuditLog(
        application_id=None,
        user_id=user.id,
        action='BUSINESS_CREATED',
        details=f'Business "{business.name}" created with {len(checklist)} approvals required'
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify({
        'business': business.to_dict(),
        'checklist': checklist,
        'licence_assignments': licence_assignments
    }), 201

@businesses_bp.route('/<business_id>/checklist', methods=['GET'])
@jwt_required()
def get_checklist(business_id):
    user = get_current_user()
    business = Business.query.get_or_404(business_id)
    
    if user.role == 'APPLICANT' and business.owner_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    checklist = generate_approval_checklist(business)
    
    # Get application status for each approval type
    apps = {a.approval_type_id: a for a in Application.query.filter_by(business_id=business_id).all()}
    
    for item in checklist:
        app = apps.get(item['approval_type']['id'])
        if app:
            item['application_id'] = app.id
            item['application_number'] = app.application_number
            item['application_status'] = app.status
        else:
            item['application_id'] = None
            item['application_number'] = None
            item['application_status'] = 'NOT_APPLIED'
    
    return jsonify({'checklist': checklist}), 200

@businesses_bp.route('/<business_id>', methods=['DELETE'])
@jwt_required()
def delete_business(business_id):
    user = get_current_user()
    business = Business.query.get_or_404(business_id)

    if user.role == 'APPLICANT' and business.owner_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    if user.role not in ['APPLICANT', 'ADMIN']:
        return jsonify({'error': 'Unauthorized'}), 403

    from ..models import (
        Application, Certificate, Renewal, Document, Inspection, InspectionEvidence,
        ApplicationStatusHistory, AuditLog, Notification, Grievance,
    )
    import os

    # Remove all application-associated operational data before the business.
    apps = Application.query.filter_by(business_id=business_id).all()
    for app in apps:
        if app.status == 'APPROVED':
            return jsonify({'error': 'This business has an approved licence. Approved records are retained as an audit record and cannot be deleted.'}), 400

    for app in apps:
        for cert in Certificate.query.filter_by(application_id=app.id).all():
            for ren in Renewal.query.filter_by(certificate_id=cert.id).all():
                db.session.delete(ren)
            db.session.delete(cert)
        for doc in list(app.documents):
            try:
                if doc.file_path and os.path.exists(doc.file_path):
                    os.remove(doc.file_path)
            except OSError:
                pass
            db.session.delete(doc)
        for insp in list(app.inspections):
            for ev in list(insp.evidence):
                db.session.delete(ev)
            db.session.delete(insp)
        for sh in list(app.status_history):
            db.session.delete(sh)
        for al in list(app.audit_logs):
            db.session.delete(al)
        for n in Notification.query.filter_by(related_application_id=app.id).all():
            db.session.delete(n)
        for g in Grievance.query.filter_by(application_id=app.id).all():
            db.session.delete(g)
        db.session.delete(app)

    # Persisted sector→licence assignments die with the business (cascade also
    # removes them at the ORM level).
    for assignment in BusinessLicenceAssignment.query.filter_by(business_id=business_id).all():
        db.session.delete(assignment)

    db.session.delete(business)
    db.session.add(AuditLog(
        application_id=None, user_id=user.id, action='BUSINESS_DELETED',
        details=f'Business "{business.name}" deleted by {user.name}'
    ))
    db.session.commit()
    return jsonify({'message': 'Business deleted.'}), 200


@businesses_bp.route('/<business_id>', methods=['PUT'])
@jwt_required()
def update_business(business_id):
    user = get_current_user()
    business = Business.query.get_or_404(business_id)
    
    if user.role == 'APPLICANT' and business.owner_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    for field in ['name', 'district', 'city', 'address']:
        if field in data:
            setattr(business, field, data[field])
    if 'investment_amount' in data:
        business.investment_amount = parse_investment(data['investment_amount'])
    if 'employee_count' in data:
        business.employee_count = parse_employee_count(data['employee_count'])
    
    db.session.commit()
    return jsonify({'business': business.to_dict()}), 200

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models import Application, Certificate, Renewal, User, AuditLog, Notification
from datetime import datetime, timezone, timedelta

certificates_bp = Blueprint('certificates', __name__)

def get_current_user():
    """Delegate to the shared 401-safe helper (no silent None)."""
    from .utils import get_current_user as _shared
    return _shared()

def now():
    return datetime.now(timezone.utc)

@certificates_bp.route('/application/<app_id>', methods=['GET'])
@jwt_required()
def get_certificate(app_id):
    user = get_current_user()
    application = Application.query.get_or_404(app_id)
    
    if user.role == 'APPLICANT' and application.applicant_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    cert = Certificate.query.filter_by(application_id=app_id).first()
    if not cert:
        return jsonify({'error': 'Certificate not found'}), 404
    
    return jsonify({'certificate': cert.to_dict()}), 200

@certificates_bp.route('/verify/<verification_id>', methods=['GET'])
def verify_certificate(verification_id):
    cert = Certificate.query.filter_by(verification_id=verification_id).first()
    if not cert:
        return jsonify({'valid': False, 'message': 'Certificate not found'}), 404
    
    is_expired = cert.valid_until and cert.valid_until.replace(tzinfo=timezone.utc) < now()
    
    return jsonify({
        'valid': not is_expired,
        'is_prototype': cert.is_prototype,
        'certificate': cert.to_dict(),
        'message': '⚠️ This is a PROTOTYPE certificate for SIH demonstration purposes only. Not a government-issued document.'
    }), 200

@certificates_bp.route('/my-certificates', methods=['GET'])
@jwt_required()
def my_certificates():
    user = get_current_user()
    if user.role == 'APPLICANT':
        apps = Application.query.filter_by(applicant_id=user.id, status='APPROVED').all()
    else:
        apps = Application.query.filter_by(status='APPROVED').all()
    
    certs = []
    for app in apps:
        cert = Certificate.query.filter_by(application_id=app.id).first()
        if cert:
            cert_dict = cert.to_dict()
            cert_dict['application_number'] = app.application_number
            cert_dict['business_name'] = app.business.name if app.business else None
            
            # Add renewal info
            renewal = Renewal.query.filter_by(certificate_id=cert.id).first()
            if renewal:
                cert_dict['renewal'] = renewal.to_dict()
                if renewal.expiry_date:
                    exp = renewal.expiry_date.replace(tzinfo=timezone.utc) if renewal.expiry_date.tzinfo is None else renewal.expiry_date
                    days_until_expiry = (exp - now()).days
                    cert_dict['days_until_expiry'] = days_until_expiry
                    cert_dict['renewal_urgency'] = 'URGENT' if days_until_expiry <= 7 else 'SOON' if days_until_expiry <= 30 else 'APPROACHING' if days_until_expiry <= 60 else 'OK'
            
            certs.append(cert_dict)
    
    return jsonify({'certificates': certs}), 200

@certificates_bp.route('/<cert_id>/renew', methods=['POST'])
@jwt_required()
def renew_certificate(cert_id):
    user = get_current_user()
    cert = Certificate.query.get_or_404(cert_id)
    
    app = Application.query.get(cert.application_id)
    if user.role == 'APPLICANT' and app.applicant_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    import uuid as uuid_module
    
    validity_months = app.approval_type.validity_months or 12
    new_valid_until = now() + timedelta(days=validity_months * 30)
    
    new_cert_num = f"CERT-NIR-{datetime.now().year}-{uuid_module.uuid4().hex[:8].upper()}-R"
    new_ver_id = f"VID-{uuid_module.uuid4().hex[:12].upper()}"
    
    new_cert = Certificate(
        application_id=app.id,
        certificate_number=new_cert_num,
        business_name=cert.business_name,
        applicant_name=cert.applicant_name,
        approval_type_name=cert.approval_type_name,
        department_name=cert.department_name,
        issue_date=now(),
        valid_until=new_valid_until,
        verification_id=new_ver_id,
        qr_data=f"NIRMAN-VERIFY:{new_cert_num}:{new_ver_id}"
    )
    db.session.add(new_cert)
    db.session.flush()
    
    renewal = Renewal(
        certificate_id=new_cert.id,
        application_id=app.id,
        expiry_date=new_valid_until,
        status='ACTIVE',
        renewed_at=now()
    )
    db.session.add(renewal)
    
    n = Notification(
        user_id=user.id,
        title='Certificate Renewed',
        message=f'Your {cert.approval_type_name} certificate has been renewed. Valid until {new_valid_until.strftime("%d %b %Y")}.',
        type='SUCCESS',
        related_application_id=app.id
    )
    db.session.add(n)
    
    db.session.commit()
    return jsonify({'certificate': new_cert.to_dict()}), 201

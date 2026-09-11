from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models import Grievance, User, Notification
import uuid

grievances_bp = Blueprint('grievances', __name__)

def get_current_user():
    """Delegate to the shared 401-safe helper (no silent None)."""
    from .utils import get_current_user as _shared
    return _shared()

def gen_grievance_number():
    import random
    from datetime import datetime
    return f"GRV-{datetime.now().year}-{random.randint(1000, 9999)}"

@grievances_bp.route('/', methods=['GET'])
@jwt_required()
def get_grievances():
    user = get_current_user()
    if user.role in ['ADMIN']:
        grievances = Grievance.query.all()
    else:
        grievances = Grievance.query.filter_by(applicant_id=user.id).all()
    return jsonify({'grievances': [g.to_dict() for g in grievances]}), 200

@grievances_bp.route('/', methods=['POST'])
@jwt_required()
def create_grievance():
    user = get_current_user()
    data = request.get_json()
    
    if not data.get('reason') or not data.get('description'):
        return jsonify({'error': 'Reason and description are required'}), 400
    
    grv_num = gen_grievance_number()
    while Grievance.query.filter_by(grievance_number=grv_num).first():
        grv_num = gen_grievance_number()
    
    grievance = Grievance(
        grievance_number=grv_num,
        applicant_id=user.id,
        application_id=data.get('application_id'),
        reason=data['reason'],
        description=data['description'],
        status='OPEN'
    )
    db.session.add(grievance)
    db.session.commit()
    
    return jsonify({'grievance': grievance.to_dict()}), 201

@grievances_bp.route('/<grievance_id>', methods=['DELETE'])
@jwt_required()
def delete_grievance(grievance_id):
    user = get_current_user()
    grievance = Grievance.query.get_or_404(grievance_id)

    if user.role == 'APPLICANT' and grievance.applicant_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    if user.role not in ['APPLICANT', 'ADMIN']:
        return jsonify({'error': 'Unauthorized'}), 403

    if grievance.status not in ['OPEN', 'SUBMITTED']:
        return jsonify({'error': 'Cannot delete a grievance that is already under review or resolved'}), 400

    db.session.delete(grievance)
    db.session.commit()
    return jsonify({'message': 'Grievance deleted successfully'}), 200

@grievances_bp.route('/<grievance_id>/resolve', methods=['POST'])
@jwt_required()
def resolve_grievance(grievance_id):
    user = get_current_user()
    if user.role not in ['ADMIN']:
        return jsonify({'error': 'Admin access required'}), 403
    
    grievance = Grievance.query.get_or_404(grievance_id)
    data = request.get_json()
    
    grievance.resolution = data.get('resolution', '')
    grievance.resolved_by_id = user.id
    grievance.status = 'RESOLVED'
    
    n = Notification(
        user_id=grievance.applicant_id,
        title='Grievance Resolved',
        message=f'Your grievance {grievance.grievance_number} has been resolved. {grievance.resolution}',
        type='SUCCESS'
    )
    db.session.add(n)
    db.session.commit()
    
    return jsonify({'grievance': grievance.to_dict()}), 200

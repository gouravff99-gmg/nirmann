from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models import User, Business, Application, Notification, ApprovalType

approvals_bp = Blueprint('approvals', __name__)

def get_current_user():
    """Delegate to the shared 401-safe helper (no silent None)."""
    from .utils import get_current_user as _shared
    return _shared()

@approvals_bp.route('/types', methods=['GET'])
@jwt_required()
def get_approval_types():
    types = ApprovalType.query.all()
    return jsonify({'approval_types': [t.to_dict() for t in types]}), 200

@approvals_bp.route('/types/<type_id>', methods=['GET'])
@jwt_required()
def get_approval_type(type_id):
    at = ApprovalType.query.get_or_404(type_id)
    return jsonify({'approval_type': at.to_dict()}), 200

@approvals_bp.route('/schemes', methods=['GET'])
@jwt_required()
def get_schemes():
    from ..models import Scheme, Business
    user = get_current_user()
    
    business_id = request.args.get('business_id')
    schemes_query = Scheme.query
    
    if business_id:
        business = Business.query.get(business_id)
        if business:
            all_schemes = Scheme.query.all()
            applicable = []
            for s in all_schemes:
                sectors = s.applicable_sectors.split(',') if s.applicable_sectors else []
                sizes = s.applicable_sizes.split(',') if s.applicable_sizes else []
                if business.sector in sectors or not sectors:
                    if business.size_category in sizes or not sizes:
                        applicable.append(s.to_dict())
            return jsonify({'schemes': applicable}), 200
    
    all_schemes = Scheme.query.all()
    return jsonify({'schemes': [s.to_dict() for s in all_schemes]}), 200

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models import Notification, User

notifications_bp = Blueprint('notifications', __name__)

def get_current_user():
    """Delegate to the shared 401-safe helper (no silent None)."""
    from .utils import get_current_user as _shared
    return _shared()

@notifications_bp.route('/', methods=['GET'])
@jwt_required()
def get_notifications():
    user = get_current_user()
    notifs = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(50).all()
    unread = sum(1 for n in notifs if not n.is_read)
    return jsonify({'notifications': [n.to_dict() for n in notifs], 'unread_count': unread}), 200

@notifications_bp.route('/<notif_id>/read', methods=['POST'])
@jwt_required()
def mark_read(notif_id):
    user = get_current_user()
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    notif.is_read = True
    db.session.commit()
    return jsonify({'notification': notif.to_dict()}), 200

@notifications_bp.route('/mark-all-read', methods=['POST'])
@jwt_required()
def mark_all_read():
    user = get_current_user()
    Notification.query.filter_by(user_id=user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'message': 'All notifications marked as read'}), 200

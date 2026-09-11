"""Server-Sent Events endpoint for genuine realtime push.

EventSource (browser) cannot send an Authorization header, so the access token
is passed as an explicit token query parameter and decoded here. Anonymous or
stale tokens receive a 401 JSON so the client can reconnect cleanly after login.
"""
from flask import Blueprint, Response, request, jsonify
from flask_jwt_extended import decode_token, create_access_token
from ..models import User
from ..services.realtime import subscribe, sse_generator

realtime_bp = Blueprint('realtime', __name__)


@realtime_bp.route('/stream', methods=['GET'])
def realtime_stream():
    token = request.args.get('token', '')
    if not token:
        return jsonify({'error': 'Missing token'}), 401
    try:
        identity = decode_token(token)['sub']
        if isinstance(identity, dict):
            user_id = identity.get('id')
        else:
            user_id = identity
    except Exception:
        return jsonify({'error': 'Invalid or expired session'}), 401

    user = User.query.get(user_id)
    if user is None or not user.is_active or not user.is_verified:
        return jsonify({'error': 'Session invalid or stale — please log in again.'}), 401

    q = subscribe(user.id)
    return Response(
        sse_generator(user.id, q),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache, no-transform',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )


@realtime_bp.route('/token', methods=['POST'])
def realtime_token():
    """Return a fresh connection token for the current session (used by the
    client to open /stream when a long-lived JWT may be absent)."""
    token = request.get_json(silent=True) or {}
    current = token.get('token', '')
    if not current:
        return jsonify({'error': 'Missing token'}), 401
    try:
        identity = decode_token(current)['sub']
        user_id = identity.get('id') if isinstance(identity, dict) else identity
    except Exception:
        return jsonify({'error': 'Invalid or expired session'}), 401
    user = User.query.get(user_id)
    if user is None or not user.is_active or not user.is_verified:
        return jsonify({'error': 'Session invalid or stale — please log in again.'}), 401
    return jsonify({'token': create_access_token(identity=user.id)}), 200
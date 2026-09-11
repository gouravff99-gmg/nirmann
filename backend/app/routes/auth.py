from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from .. import db
from ..models import User
from ..services.otp import (
    generate_otp, digest, matches as otp_matches, send_otp, now, utc_aware,
    otp_ttl_seconds, otp_resend_cooldown_seconds, otp_resend_limit, otp_attempt_limit,
)
import bcrypt
import re
from datetime import timedelta

auth_bp = Blueprint('auth', __name__)

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _normalize_mobile(mobile):
    """Normalize an Indian mobile number to a 10-digit string, or None."""
    if not mobile:
        return None
    s = str(mobile).strip().replace(' ', '').replace('-', '')
    if s.startswith('+91'):
        s = s[3:]
    elif s.startswith('91') and len(s) == 12:
        s = s[2:]
    return s if re.fullmatch(r'[6-9]\d{9}', s) else None


def _otp_failed(user, error, code):
    user.otp_attempts = (user.otp_attempts or 0) + 1
    if user.otp_attempts >= otp_attempt_limit():
        # Invalidate the code so a fresh OTP must be requested.
        user.otp_hash = None
        user.otp_expires_at = None
    db.session.commit()
    return jsonify({'error': error}), code


@auth_bp.route('/register', methods=['POST'])
def register():
    """Create a new APPLICANT account.

    Requires Full Name, Email, Mobile, Password and Confirm Password. The
    account starts UNVERIFIED and cannot log in until OTP verification is
    completed. Usernames are never taken from the client (always APPLICANT).
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    name = str(data.get('name', '')).strip()
    email = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', ''))
    confirm = str(data.get('confirm_password', '') or data.get('confirmPassword', ''))
    mobile = str(data.get('mobile', '') or data.get('phone', '')).strip()

    if len(name) < 2 or len(name) > 100:
        return jsonify({'error': 'Full name must be between 2 and 100 characters'}), 400
    if not _EMAIL_RE.fullmatch(email):
        return jsonify({'error': 'Please enter a valid email address'}), 400
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters long'}), 400
    if password != confirm:
        return jsonify({'error': 'Passwords do not match'}), 400

    phone = _normalize_mobile(mobile)
    if not phone:
        return jsonify({'error': 'Please enter a valid 10-digit Indian mobile number'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'An account with this email already exists.'}), 409
    if User.query.filter_by(phone=phone).first():
        return jsonify({'error': 'An account with this mobile number already exists.'}), 409

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user = User(
        email=email, password_hash=hashed, name=name, role='APPLICANT', phone=phone,
        email_verified=False, mobile_verified=False, verification_status='UNVERIFIED',
    )

    otp = generate_otp()
    user.otp_hash = digest(otp)
    user.otp_expires_at = now() + timedelta(seconds=otp_ttl_seconds())
    user.otp_attempts = 0
    user.otp_resends = 0
    user.otp_last_sent_at = now()

    delivery = send_otp(user, otp)
    db.session.add(user)
    db.session.commit()

    payload = {
        'user_id': user.id,
        'email': user.email,
        'verification_required': True,
        'message': 'Account created. Verify your email and mobile number with the code you received before signing in.',
        'delivery': delivery,
    }
    return jsonify(payload), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    email = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', ''))

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
    # Defensively verify the stored hash: a non-bcrypt placeholder (e.g. the
    # system-only AI role) should fail closed as invalid credentials, never
    # surface a 500 'Invalid salt' error.
    try:
        hash_ok = bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8'))
    except (ValueError, TypeError):
        hash_ok = False
    if not hash_ok:
        return jsonify({'error': 'Invalid credentials'}), 401
    if not user.is_active:
        return jsonify({'error': 'Account is disabled'}), 403
    if not user.is_verified:
        return jsonify({
            'error': 'Please verify your account before continuing.',
            'verification_required': True,
            'email': user.email,
        }), 403

    token = create_access_token(identity=user.id)
    return jsonify({'token': token, 'user': user.to_dict()}), 200


@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp():
    """Verify the account using the emailed/SMS code.

    One OTP completes both email and mobile verification for the demo flow.
    On success the account is marked VERIFIED and a login token is returned so
    the user lands straight inside the NIRMAN dashboard.
    """
    data = request.get_json() or {}
    email = str(data.get('email', '')).strip().lower()
    otp = str(data.get('otp', '')).strip()

    user = User.query.filter_by(email=email).first()
    if not user or user.otp_hash is None:
        return jsonify({'error': 'OTP is invalid or expired. Please request a new code.'}), 400

    if user.is_verified:
        token = create_access_token(identity=user.id)
        return jsonify({'verified': True, 'message': 'Account already verified.', 'token': token, 'user': user.to_dict()}), 200

    if utc_aware(user.otp_expires_at) and now() > utc_aware(user.otp_expires_at):
        user.otp_hash = None
        user.otp_expires_at = None
        db.session.commit()
        return jsonify({'error': 'OTP has expired. Please request a new code.'}), 400

    if (user.otp_attempts or 0) >= otp_attempt_limit():
        return jsonify({'error': 'Too many incorrect OTP attempts. Please request a new code.'}), 400

    if not otp_matches(user.otp_hash, otp):
        remaining = otp_attempt_limit() - (user.otp_attempts or 0) - 1
        return _otp_failed(
            user,
            f'Incorrect OTP. {max(remaining, 0)} attempt(s) remaining.' if remaining > 0
            else 'Incorrect OTP. Please request a new code.',
            400,
        )

    user.mark_verified()
    db.session.commit()

    token = create_access_token(identity=user.id)
    return jsonify({
        'verified': True,
        'message': 'Account verified. Welcome to NIRMAN!',
        'token': token,
        'user': user.to_dict(),
    }), 200


@auth_bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    """Send a fresh OTP, enforcing a cooldown and a resend budget."""
    data = request.get_json() or {}
    email = str(data.get('email', '')).strip().lower()

    user = User.query.filter_by(email=email).first()
    if not user or not user.otp_hash:
        if user and user.is_verified:
            return jsonify({'error': 'Account is already verified. Please sign in.'}), 400
        return jsonify({'error': 'No pending verification for this account. Please register first.'}), 404
    if user.is_verified:
        return jsonify({'error': 'Account is already verified. Please sign in.'}), 400

    cooldown = otp_resend_cooldown_seconds()
    last_sent = user.otp_last_sent_at
    if last_sent and (now() - utc_aware(last_sent)).total_seconds() < cooldown:
        wait = int(cooldown - (now() - utc_aware(last_sent)).total_seconds()) + 1
        return jsonify({'error': f'Please wait {wait} second(s) before requesting another code.'}), 429

    if (user.otp_resends or 0) >= otp_resend_limit():
        return jsonify({'error': 'OTP resend limit reached. Please try again later.'}), 429

    otp = generate_otp()
    user.otp_hash = digest(otp)
    user.otp_expires_at = now() + timedelta(seconds=otp_ttl_seconds())
    user.otp_attempts = 0
    user.otp_resends = (user.otp_resends or 0) + 1
    user.otp_last_sent_at = now()

    delivery = send_otp(user, otp)
    db.session.commit()
    return jsonify({'message': 'A new code has been sent.', 'delivery': delivery, 'email': user.email}), 200


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Start a password reset with an OTP (same digest/limits as verification)."""
    data = request.get_json() or {}
    email = str(data.get('email', '')).strip().lower()

    user = User.query.filter_by(email=email).first()
    if not user:
        # Do not reveal whether the account exists.
        return jsonify({'message': 'If an account exists, a reset code has been sent.'}), 200

    cooldown = otp_resend_cooldown_seconds()
    last_sent = user.otp_last_sent_at
    if last_sent and (now() - utc_aware(last_sent)).total_seconds() < cooldown:
        wait = int(cooldown - (now() - utc_aware(last_sent)).total_seconds()) + 1
        return jsonify({'error': f'Please wait {wait} second(s) before requesting another code.'}), 429
    if (user.otp_resends or 0) >= otp_resend_limit():
        return jsonify({'error': 'OTP resend limit reached. Please try again later.'}), 429

    otp = generate_otp()
    user.otp_hash = digest(otp)
    user.otp_expires_at = now() + timedelta(seconds=otp_ttl_seconds())
    user.otp_attempts = 0
    user.otp_resends = (user.otp_resends or 0) + 1
    user.otp_last_sent_at = now()

    delivery = send_otp(user, otp)
    db.session.commit()
    return jsonify({'message': 'If an account exists, a reset code has been sent.', 'delivery': delivery, 'email': user.email}), 200


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Complete a password reset using the emailed code."""
    data = request.get_json() or {}
    email = str(data.get('email', '')).strip().lower()
    otp = str(data.get('otp', '')).strip()
    new_pwd = str(data.get('new_password', ''))
    confirm = str(data.get('confirm_password', ''))

    user = User.query.filter_by(email=email).first()
    if not user or user.otp_hash is None:
        return jsonify({'error': 'No reset request found for this account. Please start again.'}), 400
    if len(new_pwd) < 8:
        return jsonify({'error': 'Password must be at least 8 characters long'}), 400
    if new_pwd != confirm:
        return jsonify({'error': 'Passwords do not match'}), 400
    if utc_aware(user.otp_expires_at) and now() > utc_aware(user.otp_expires_at):
        user.otp_hash = None
        user.otp_expires_at = None
        db.session.commit()
        return jsonify({'error': 'OTP has expired. Please request a new code.'}), 400
    if (user.otp_attempts or 0) >= otp_attempt_limit():
        return jsonify({'error': 'Too many incorrect OTP attempts. Please request a new code.'}), 400
    if not otp_matches(user.otp_hash, otp):
        remaining = otp_attempt_limit() - (user.otp_attempts or 0) - 1
        return _otp_failed(
            user,
            f'Incorrect OTP. {max(remaining, 0)} attempt(s) remaining.' if remaining > 0
            else 'Incorrect OTP. Please request a new code.',
            400,
        )

    user.password_hash = bcrypt.hashpw(new_pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user.otp_hash = None
    user.otp_expires_at = None
    user.otp_attempts = 0
    db.session.commit()
    return jsonify({'message': 'Password reset successfully. Please sign in with your new password.'}), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    identity = get_jwt_identity()
    # Access tokens in this prototype store the user id directly. Supporting
    # both forms also keeps older demo tokens compatible.
    user = User.query.get(identity.get('id') if isinstance(identity, dict) else identity)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'user': user.to_dict()}), 200


@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    identity = get_jwt_identity()
    user = User.query.get(identity.get('id') if isinstance(identity, dict) else identity)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    data = request.get_json() or {}
    old_pwd = data.get('old_password') or ''
    new_pwd = data.get('new_password') or ''
    if not old_pwd or not new_pwd:
        return jsonify({'error': 'Both old and new passwords are required'}), 400
    if not bcrypt.checkpw(old_pwd.encode(), user.password_hash.encode()):
        return jsonify({'error': 'Old password incorrect'}), 400
    if len(new_pwd) < 8:
        return jsonify({'error': 'Password must be at least 8 characters long'}), 400
    user.password_hash = bcrypt.hashpw(new_pwd.encode(), bcrypt.gensalt()).decode()
    db.session.commit()
    return jsonify({'message': 'Password updated'}), 200
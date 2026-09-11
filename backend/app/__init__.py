from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, verify_jwt_in_request, get_jwt_identity
from flask_cors import CORS
import os

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional convenience
    load_dotenv = None

db = SQLAlchemy()
jwt = JWTManager()

# Endpoints a user may hit without a token/verification (login/registration,
# OTP verification, password reset, the certificate QR check and the labelled
# AI system-role demo entry point).
PUBLIC_PATHS = {
    '/api/auth/register',
    '/api/auth/login',
    '/api/auth/verify-otp',
    '/api/auth/resend-otp',
    '/api/auth/forgot-password',
    '/api/auth/reset-password',
    '/api/ai-agent/demo-session',
}

def create_app():
    app = Flask(__name__)

    # Load environment variables from backend/.env if it exists so secrets can
    # live outside the repo. Fallbacks keep the demo runnable out of the box.
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    if load_dotenv is not None:
        load_dotenv(os.path.join(basedir, '.env'))

    # Secrets come from the environment; the built-in values are DEMO-ONLY
    # fallbacks so the SIH prototype still boots when no .env exists. The keys
    # are 64+ bytes so they stay above the RFC 7518 minimum of 32 bytes and
    # the werkzeug/jwt libraries stop printing an InsecureKeyLengthWarning.
    app.config['SECRET_KEY'] = (
        os.environ.get('NIRMAN_SECRET_KEY')
        or os.environ.get('SECRET_KEY')
        or 'nirman-sih-2026-demo-only-secret-key-do-not-use-in-production-0001'
    )
    app.config['JWT_SECRET_KEY'] = (
        os.environ.get('NIRMAN_JWT_SECRET_KEY')
        or os.environ.get('JWT_SECRET_KEY')
        or app.config['SECRET_KEY']
    )
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "nirman.db")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False  # For demo
    app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    jwt.init_app(app)
    CORS(app, origins='*', supports_credentials=True)

    # ------------------------------------------------------------------
    # Global auth + role gate: an access token is accepted only when it still
    # references a live, ACTIVE and VERIFIED user. Unverified accounts cannot
    # reach any data route even if they obtain a token by other means, and a
    # token minted before a DB reseed yields a clean 401 instead of a 500.
    # ------------------------------------------------------------------
    @app.before_request
    def enforce_auth_gate():
        path = request.path
        if request.method == 'OPTIONS':
            # CORS preflight carries no credentials — let Flask-CORS handle it.
            return None
        if not path.startswith('/api/') or path in PUBLIC_PATHS:
            return None
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if identity is None:
            # Let the route's own @jwt_required() raise a proper 401.
            return None
        user_id = identity.get('id') if isinstance(identity, dict) else identity
        if not user_id:
            return jsonify({'error': 'Missing or invalid session'}), 401
        from .models import User
        user = User.query.get(user_id)
        if user is None:
            return jsonify({'error': 'Session invalid or stale — please log in again.'}), 401
        if not user.is_active:
            return jsonify({'error': 'Account is disabled'}), 403
        if not user.is_verified:
            return jsonify({
                'error': 'Please verify your account before continuing.',
                'verification_required': True,
                'email': user.email,
            }), 403
        return None

    # Register blueprints
    from .routes.auth import auth_bp
    from .routes.businesses import businesses_bp
    from .routes.approvals import approvals_bp
    from .routes.applications import applications_bp
    from .routes.documents import documents_bp
    from .routes.inspector import inspector_bp
    from .routes.admin import admin_bp
    from .routes.notifications import notifications_bp
    from .routes.grievances import grievances_bp
    from .routes.certificates import certificates_bp
    from .routes.assistant import assistant_bp
    from .routes.ai_agent import ai_agent_bp
    from .routes.officer import officer_bp
    from .routes.realtime import realtime_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(businesses_bp, url_prefix='/api/businesses')
    app.register_blueprint(approvals_bp, url_prefix='/api/approvals')
    app.register_blueprint(applications_bp, url_prefix='/api/applications')
    app.register_blueprint(documents_bp, url_prefix='/api/documents')
    app.register_blueprint(inspector_bp, url_prefix='/api/inspector')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(notifications_bp, url_prefix='/api/notifications')
    app.register_blueprint(grievances_bp, url_prefix='/api/grievances')
    app.register_blueprint(certificates_bp, url_prefix='/api/certificates')
    app.register_blueprint(assistant_bp, url_prefix='/api/assistant')
    app.register_blueprint(ai_agent_bp, url_prefix='/api/ai-agent')
    app.register_blueprint(officer_bp, url_prefix='/api/officer')
    app.register_blueprint(realtime_bp, url_prefix='/api/realtime')

    # Always return JSON for common HTTP errors (401/403/404/400/409) instead
    # of Flask's default HTML page, so SPA clients can parse the reason.
    @app.errorhandler(400)
    def _err_400(e):   return jsonify({'error': getattr(e, 'description', 'Bad request')}), 400

    @app.errorhandler(401)
    def _err_401(e):   return jsonify({'error': getattr(e, 'description', 'Unauthorized')}), 401

    @app.errorhandler(403)
    def _err_403(e):   return jsonify({'error': getattr(e, 'description', 'Forbidden')}), 403

    @app.errorhandler(404)
    def _err_404(e):   return jsonify({'error': getattr(e, 'description', 'Not found')}), 404

    @app.errorhandler(409)
    def _err_409(e):   return jsonify({'error': getattr(e, 'description', 'Conflict')}), 409

    return app

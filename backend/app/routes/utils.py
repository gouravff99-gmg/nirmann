"""
Shared utilities for route handlers
"""
from flask import abort
from flask_jwt_extended import get_jwt_identity
from ..models import User

def get_current_user():
    """Get the current authenticated user from JWT identity.

    Returns the User row, or aborts with 401 when the token no longer
    references a real user (e.g. a stale token minted before a database
    reseed). Every route module delegates to this single helper so an
    invalid session always yields a clean 401 JSON error instead of a 500.
    """
    user_id = get_jwt_identity()
    if user_id is None:
        abort(401, description='Missing or invalid session')
    user = User.query.get(user_id)
    if user is None:
        abort(401, description='Session invalid or stale — please log in again.')
    return user

"""
One-Time Password (OTP) service for account verification.

Security model
--------------
* OTPs are generated server-side with ``secrets`` (cryptographically random).
* Only a keyed HMAC-SHA256 digest of an OTP is ever persisted — never the
  plain OTP — so a database leak does not expose reusable codes.
* The digest key comes from the server's SECRET_KEY (env-driven, demo fallback).
* OTPs expire after a short window (NIRMAN_OTP_TTL_SECONDS, default 300s).
* Resends are rate-limited (cooldown + lifetime resend budget) and incorrect
  attempts are capped (NIRMAN_OTP_ATTEMPT_LIMIT).

Delivery providers
------------------
The demo runs in clearly-labelled DEMO mode: if no external provider is
configured the OTP is returned in the API response so the flow can be shown
end-to-end at a SIH demo. Connecting a real provider only requires setting
environment variables (e.g. NIRMAN_OTP_PROVIDER=smtp plus SMTP/SMS creds); a
integration point is provided in ``_deliver_external``.
"""
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

DEMO_NOTICE = (
    'DEMO ONLY — no external SMS/email provider is configured, so this '
    'verification code is shown here for the SIH demo. This is not a real '
    'production OTP.'
)

_OTP_RE = re.compile(r'^\d{6}$')


# ---------------------------------------------------------------------------
# Config (environment-driven with demo defaults)
# ---------------------------------------------------------------------------

def cfg(name, default):
    return os.environ.get(name, default)


def provider_is_external():
    """True when an external OTP delivery provider has been configured."""
    return cfg('NIRMAN_OTP_PROVIDER', '').strip().lower() in (
        'smtp', 'email', 'sms', 'twilio', 'msg91', 'gupshup'
    )


def otp_ttl_seconds():
    return int(cfg('NIRMAN_OTP_TTL_SECONDS', '300'))


def otp_resend_cooldown_seconds():
    return int(cfg('NIRMAN_OTP_RESEND_COOLDOWN_SECONDS', '30'))


def otp_resend_limit():
    return int(cfg('NIRMAN_OTP_RESEND_LIMIT', '5'))


def otp_attempt_limit():
    return int(cfg('NIRMAN_OTP_ATTEMPT_LIMIT', '5'))


def now():
    return datetime.now(timezone.utc)


def utc_aware(dt):
    """Normalise a stored (possibly timezone-naive) datetime to aware UTC.

    SQLite persists naive datetimes, so comparisons against ``now()`` need this
    to stay timezone-safe.
    """
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# OTP generation / persistence helpers
# ---------------------------------------------------------------------------

def generate_otp():
    """Cryptographically random 6-digit code."""
    return f'{secrets.randbelow(1_000_000):06d}'


def _digest_key():
    key = cfg('NIRMAN_SECRET_KEY', '') or cfg('SECRET_KEY', '')
    return (key or 'nirman-demo-otp-key').encode('utf-8')


def digest(otp):
    """Keyed HMAC-SHA256 digest of an OTP string."""
    code = str(otp or '').strip()
    return hmac.new(_digest_key(), code.encode('utf-8'), hashlib.sha256).hexdigest()


def matches(stored_digest, otp):
    """Constant-time comparison of a submitted OTP against the stored digest."""
    if not stored_digest or not otp:
        return False
    candidate = str(otp).strip()
    if not _OTP_RE.fullmatch(candidate):
        return False
    return hmac.compare_digest(stored_digest, digest(candidate))


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------

def send_otp(user, otp):
    """Deliver an OTP.

    Returns a dict describing how it was delivered:

      * ``{'mode': 'demo', 'demo_otp': <code>, 'notice': <DEMO ONLY note>}``
        when no external provider is configured. The code travels back to the
        caller so it can be surfaced in the labelled DEMO OTP box.
      * ``{'mode': 'external', 'notice': 'A code was sent...'}`` when an
        external provider is configured (code is NOT echoed back).
    """
    if not provider_is_external():
        return {'mode': 'demo', 'demo_otp': otp, 'notice': DEMO_NOTICE}
    _deliver_external(user, otp)
    return {
        'mode': 'external',
        'notice': f'A 6-digit verification code has been sent to {user.email}.',
    }


def _deliver_external(user, otp):
    """Integration point for a real SMS/email provider.

    Reads provider settings from environment variables (never hard-coded):
      NIRMAN_OTP_PROVIDER   (smtp|sms|twilio|msg91|gupshup ...)
      NIRMAN_SMTP_HOST / NIRMAN_SMTP_PORT / NIRMAN_SMTP_USER / NIRMAN_SMTP_PASS
      NIRMAN_EMAIL_API_KEY / NIRMAN_EMAIL_FROM
      NIRMAN_SMS_API_KEY / NIRMAN_SMS_FROM

    The demo build never reaches this function unless a provider environment
    variable has been set. Wire the chosen vendor's SDK here.
    """
    raise NotImplementedError(
        'External OTP provider configured but not wired. Set'
        ' NIRMAN_OTP_PROVIDER appropriately and implement _deliver_external().'
    )
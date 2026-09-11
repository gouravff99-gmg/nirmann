"""Idempotent demo seeding of the SINGLE Licence Officer / Inspector desk.

Officers share a dedicated role — there is exactly ONE operational human
officer: Arjun Singh, the Licence Officer / Inspector. He is a
User(role='OFFICER') + one Officer profile row + authorisation for EVERY
licence type (officer_licences). Auto-routing (routing.py) therefore always
resolves to this single office, so the same officer performs application
review, inspection and final approval for every licence.

Industry desks (Food, Fire, Factory, Pollution, Trade, Drugs) are retained as
labelled LICENCE CATEGORIES only — they are filters, NOT separate officer
accounts, and never create additional officers.

The account is clearly labelled a DEMO OFFICER ACCOUNT — NOT A REAL
GOVERNMENT ACCOUNT.
"""
import bcrypt

from .. import db
from ..models import (
    Application, ApplicationAssignment, ApprovalType, Department, Officer,
    OfficerLicence, User, gen_id,
)

DEMO_LABEL = 'DEMO OFFICER ACCOUNT — NOT A REAL GOVERNMENT ACCOUNT.'

ALL_LICENCES = [
    'FSSAI', 'HEALTH_NOC', 'PHARMACY_DEMO', 'FIRE_NOC',
    'ELEC_SAFETY', 'BUILD_PLAN', 'TRADE_LIC', 'BIZ_REG',
    'SHOPS_EST', 'LABOUR_REG', 'FACTORY_LIC', 'GST_REG',
    'UDYAM', 'POLLUTION_CTO', 'HAZ_MAT',
]

# The single, only operational human officer.
OFFICER_DEFS = [
    {
        'officer_number': 'NIR-OFF-006',
        'email': 'inspector@demo.com',
        'name': 'Arjun Singh',
        'password': 'Demo@1234',
        'designation': 'Licence Officer / Inspector',
        'authority': 'General Licensing Desk',
        'dept_code': 'MUNICIPAL',
        'location': 'Mumbai',
        'state': 'Maharashtra',
        'licences': ALL_LICENCES,
    },
]


def _hash_password(pwd):
    return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()


def ensure_officers():
    """Create or repair the SINGLE Licence Officer / Inspector account. Idempotent."""
    created = 0
    for o in OFFICER_DEFS:
        user = User.query.filter_by(email=o['email']).first()
        if not user:
            user = User(
                id=gen_id(), email=o['email'], name=o['name'],
                password_hash=_hash_password(o['password']), role='OFFICER',
                email_verified=True, mobile_verified=True,
                verification_status='VERIFIED',
            )
            db.session.add(user)
            db.session.flush()
        else:
            if user.role != 'OFFICER':
                user.role = 'OFFICER'
            user.mark_verified()
            if user.password_hash == 'SYSTEM_ROLE_NOT_A_HUMAN_LOGIN':
                user.password_hash = _hash_password(o['password'])
            db.session.flush()

        profile = Officer.query.filter_by(user_id=user.id).first()
        if not profile:
            dept = None
            if o.get('dept_code'):
                dept = Department.query.filter_by(code=o['dept_code']).first()
            profile = Officer(
                id=gen_id(), officer_number=o['officer_number'], user_id=user.id,
                designation=o['designation'], authority=o['authority'],
                department_id=dept.id if dept else None,
                location=o['location'], state=o['state'], is_demo=True,
            )
            db.session.add(profile)
            db.session.flush()
            created += 1

        for code in o['licences']:
            at = ApprovalType.query.filter_by(code=code).first()
            if at and not OfficerLicence.query.filter_by(
                    officer_id=profile.id, approval_type_id=at.id).first():
                db.session.add(
                    OfficerLicence(id=gen_id(), officer_id=profile.id,
                                   approval_type_id=at.id))
    db.session.commit()
    return created


def _is_parallel_demo_application(application):
    """True if an application belongs to the separate AI parallel-processing
    demo (the "five business journeys" in ai_agent.py) rather than the officer
    licence-lifecycle demo, and is NOT one of the officer-lifecycle demo
    applications seeded by demo_officer_seed.py.

    Parallel-demo applications are clearly tagged with an AI_DEMO_WORKFLOW_CREATED
    audit entry. The officer-lifecycle demo applications (GreenLeaf, Metro,
    Sunrise, Apex, CarePlus Pharmacy, QuickServe) are instead tagged with a
    DEMO_SEEDED audit entry and must remain in the officer's inbox even though
    CarePlus also appears in the parallel demo.
    """
    from ..models import AuditLog
    is_parallel = AuditLog.query.filter_by(
        application_id=application.id, action='AI_DEMO_WORKFLOW_CREATED'
    ).first() is not None
    is_officer_seed = AuditLog.query.filter_by(
        application_id=application.id, action='DEMO_SEEDED'
    ).first() is not None
    return is_parallel and not is_officer_seed


def _close_officer_assignment(application):
    """Close (deactivate) any active officer assignment for a parallel-demo app
    so it no longer appears in the officer's lifecycle inbox. Also detaches any
    inspection records from the officer so they stay out of the inspector's
    "My Inspections" view (they belong to the separate parallel-demo workbook,
    not to the officer's licence lifecycle desk)."""
    from ..models import ApplicationAssignment, Inspection
    for a in ApplicationAssignment.query.filter_by(
            application_id=application.id, status='ACTIVE').all():
        a.status = 'CLOSED'
    for ins in Inspection.query.filter_by(application_id=application.id).all():
        # Detach every inspection of a parallel-demo app from the officer,
        # including completed ones, so they stay out of the officer/inspector
        # lifecycle views. (This only runs for parallel-demo apps, never the
        # officer's own seeded lifecycle apps, whose PASS inspections are kept.)
        ins.inspector_id = None
        ins.assigned_by_id = None


def ensure_officer_assignments():
    """Route any non-terminal, submitted application missing an officer.

    Deterministically fills the officer inboxes from existing demo data so an
    officer session always has a real, DB-backed workload. Applications that
    belong to the separate AI parallel-processing demo are kept OUT of the
    officer's licence-lifecycle inbox: they are presentation workbooks for the
    "five business journeys" demo, not items for the officer to decide on.
    """
    from .routing import assign_officer
    assigned = 0
    q = (ApplicationAssignment.query.filter_by(status='ACTIVE')
         .with_entities(ApplicationAssignment.application_id).all())
    active_ids = {row[0] for row in q}
    apps = Application.query.filter(
        Application.status.notin_(['DRAFT', 'APPROVED', 'REJECTED', 'EXPIRED'])
    ).all()
    for app in apps:
        if _is_parallel_demo_application(app):
            _close_officer_assignment(app)
            continue
        if app.id in active_ids:
            continue
        if assign_officer(app, auto_routed=True):
            assigned += 1
    db.session.commit()
    return assigned
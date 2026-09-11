"""Deterministic DB-driven auto-routing of applications to licence officers.

Routing is driven SOLELY by the licence/approval name:

    licence / approval name
        -> responsible department
        -> responsible officer

An application is routed to the officer(s) authorised for its licence type
(officer_licences). Location (city/state/district/pincode/address) is NEVER
used to select an officer. Candidates are ranked only by current workload
(open assignments), so the routing is reproducible and location-independent.

The routing is the single source of truth: application_assignments + the
legacy assigned_officer_id column are kept in sync by assign_officer().
"""
from .. import db
from ..models import (
    Application, ApplicationAssignment, Officer, OfficerLicence, Notification,
    User, now,
)
from .realtime import publish

TERMINAL_STATUSES = ('APPROVED', 'REJECTED', 'EXPIRED')


def _open_assignment_count(officer_user_id):
    return (
        ApplicationAssignment.query
        .filter_by(officer_id=officer_user_id, status='ACTIVE')
        .join(Application, Application.id == ApplicationAssignment.application_id)
        .filter(Application.status.notin_(TERMINAL_STATUSES))
        .count()
    )


def find_best_officer(approval_type_id, business=None):
    """Return the best Officer for a licence application or None.

    Selection is licence-driven only: every officer authorised for the
    application's licence type (officer_licences) is a candidate, ranked by
    current workload (open assignments) and then deterministic officer number.
    The officer's assigned licence types are the hard gate — an officer can
    never be selected for a licence type they are not authorised for.

    The ``business`` argument is accepted for API compatibility but plays NO
    role in ranking. Location never influences the responsible officer.
    """
    rows = OfficerLicence.query.filter_by(approval_type_id=approval_type_id).all()
    if not rows:
        return None

    candidates = []
    for ol in rows:
        officer = ol.officer
        if not officer or not officer.user or not officer.user.is_active:
            continue
        open_count = _open_assignment_count(officer.user_id)
        candidates.append((open_count, officer.officer_number, officer))

    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], c[1]))
    return candidates[0][2]


def assign_officer(application, actor=None, auto_routed=True, notes=None):
    """Assign (or re-assign) the best officer to an application.

    Creates/updates the application_assignments row and keeps the legacy
    application.assigned_officer_id column in sync. Notifies the officer.
    Caller commits.
    """
    if application is None:
        return None
    officer = find_best_officer(application.approval_type_id, application.business)
    if officer is None:
        return None

    assignment = ApplicationAssignment.query.filter_by(
        application_id=application.id).first()
    same_officer = bool(
        assignment and assignment.officer_id == officer.user_id
        and assignment.status == 'ACTIVE')
    if assignment is None:
        assignment = ApplicationAssignment(application_id=application.id)
        db.session.add(assignment)
    assignment.officer_id = officer.user_id
    assignment.assigned_by_id = actor.id if actor else None
    assignment.auto_routed = auto_routed
    assignment.status = 'ACTIVE'
    assignment.assigned_at = now()

    application.assigned_officer_id = officer.user_id
    db.session.flush()

    if not same_officer:
        db.session.add(Notification(
            user_id=officer.user_id,
            title='New application assigned',
            message=(
                f"{application.application_number} — {application.business.name} "
                f"({application.approval_type.code}) has been routed to you for review."
            ),
            type='INFO',
            related_application_id=application.id,
        ))
        publish([officer.user_id], event='new_assignment',
                payload={'application_id': application.id,
                         'application_number': application.application_number})
    return officer


def licence_code(application):
    return application.approval_type.code if application.approval_type else None
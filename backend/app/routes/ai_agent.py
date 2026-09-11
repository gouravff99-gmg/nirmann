"""
NIRMAN AI Compliance Agent Routes
===================================
Provides the AI Agent dashboard, activity stream and business overview.
All AI analysis is SIMULATED / DEMO logic - clearly labeled.
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from .. import db
from ..models import (
    Application, ApplicationStatusHistory, ApprovalType, AuditLog, Business,
    Certificate, Department, Document, DocumentRequirement, Inspection,
    Notification, Renewal, User, gen_id,
)
from ..services import ai_decision_service
from ..services.routing import find_best_officer
from datetime import datetime, timezone, timedelta
import uuid
import json

ai_agent_bp = Blueprint('ai_agent', __name__)

def get_current_user():
    """Delegate to the shared 401-safe helper (no silent None)."""
    from .utils import get_current_user as _shared
    return _shared()

def now():
    return datetime.now(timezone.utc)


# These are intentionally compact, configurable demo rules. They are not a
# representation of any current law or of a connected government system.
DEMO_PROFILES = {
    'Urban Spice Restaurant': {
        'type': 'Restaurant / Food Service', 'icon': '🍽️', 'risk_score': 22,
        'risk': 'LOW', 'state': 'ACTIVE', 'progress': 82,
        'inspection': 'Fire inspection scheduled', 'owner_email': 'applicant@demo.com',
        'codes': ['TRADE_LIC', 'FSSAI', 'FIRE_NOC', 'HEALTH_NOC', 'LABOUR_REG', 'SHOPS_EST'],
        'statuses': ['APPROVED', 'APPROVED', 'INSPECTION_SCHEDULED', 'APPROVED', 'APPROVED', 'APPROVED'],
        'why': 'Customer-facing food service from a commercial premises triggers the simulated food, safety, local-body and workforce rules.',
    },
    'Precision Components Manufacturing': {
        'type': 'Small Manufacturing Unit', 'icon': '🏭', 'risk_score': 84,
        'risk': 'HIGH', 'state': 'ACTIVE', 'progress': 54,
        'inspection': 'Factory & environmental inspection required', 'owner_email': 'applicant@demo.com',
        'codes': ['TRADE_LIC', 'POLLUTION_CTO', 'FACTORY_LIC', 'FIRE_NOC', 'LABOUR_REG', 'ELEC_SAFETY', 'HAZ_MAT'],
        'statuses': ['APPROVED', 'UNDER_REVIEW', 'INSPECTION_SCHEDULED', 'INSPECTION_SCHEDULED', 'APPROVED', 'CORRECTION_REQUIRED', 'UNDER_REVIEW'],
        'why': 'Industrial operations, machinery and hazardous-material handling trigger enhanced simulated scrutiny.',
    },
    'CarePlus Pharmacy': {
        'type': 'Pharmacy / Medical Retail', 'icon': '💊', 'risk_score': 62,
        'risk': 'MEDIUM', 'state': 'ACTIVE', 'progress': 60,
        'inspection': 'Pharmacy premises inspection required', 'owner_email': 'applicant@demo.com',
        'codes': ['TRADE_LIC', 'PHARMACY_DEMO', 'FIRE_NOC', 'LABOUR_REG', 'SHOPS_EST'],
        'statuses': ['APPROVED', 'UNDER_REVIEW', 'INSPECTION_REQUIRED', 'APPROVED', 'APPROVED'],
        'why': 'Medical retail is routed to a specialised simulated pharmacy review alongside premises and workforce checks.',
    },
}

STATE_ORDER = [
    'DRAFT', 'SUBMITTED', 'AI_ANALYSIS', 'CHECKLIST_GENERATED',
    'DOCUMENT_VALIDATION', 'CORRECTION_REQUIRED', 'DEPARTMENT_ROUTING',
    'PARALLEL_PROCESSING', 'INSPECTION_REQUIRED', 'INSPECTION_SCHEDULED',
    'INSPECTION_COMPLETED', 'AI_REVIEW', 'EXCEPTION', 'APPROVAL_READY',
    'APPROVED', 'RENEWAL_DUE', 'RENEWED',
]


def _actor():
    """Return the system actor if it exists; an admin is a safe fallback."""
    return User.query.filter_by(email='ai-agent@system.demo').first() or User.query.filter_by(role='ADMIN').first()


def _add_audit(application, action, details, actor=None):
    if application:
        db.session.add(AuditLog(
            application_id=application.id,
            user_id=(actor or _actor()).id if (actor or _actor()) else None,
            action=action,
            details=details,
        ))


def _add_notification(user_id, title, message, notif_type='INFO', application_id=None):
    if user_id:
        db.session.add(Notification(
            user_id=user_id, title=title, message=message, type=notif_type,
            related_application_id=application_id,
        ))


def _type_by_code(code):
    return ApprovalType.query.filter_by(code=code).first()


def _ensure_pharmacy_type():
    """Add the one specialised, clearly simulated approval used by the pharmacy demo."""
    approval = _type_by_code('PHARMACY_DEMO')
    if approval:
        return approval
    department = Department.query.filter_by(code='FOOD_SAFETY').first() or Department.query.first()
    if not department:
        return None
    approval = ApprovalType(
        id=gen_id(), name='Pharmacy / Medical Retail Compliance (DEMO)',
        code='PHARMACY_DEMO', department_id=department.id,
        description='SIMULATED specialised pharmacy compliance workflow for SIH demonstration.',
        why_required='The selected business dispenses medicines and therefore requires a specialised simulated regulatory review.',
        requires_inspection=True, estimated_days=14, sla_days=18,
        validity_months=12, workflow_type='B', priority=2,
    )
    db.session.add(approval)
    db.session.flush()
    return approval


def _application_number():
    while True:
        number = f'DEMO-{datetime.now().year}-{uuid.uuid4().hex[:6].upper()}'
        if not Application.query.filter_by(application_number=number).first():
            return number


def _ensure_system_user():
    user = User.query.filter_by(email='ai-agent@system.demo').first()
    if user:
        if not user.is_verified:
            user.mark_verified()
            db.session.add(user)
            db.session.flush()
        return user
    # No password is exposed: this is a system identity entered only through
    # the explicitly-labelled AI demo entry point. Marked VERIFIED so the gate
    # never blocks the system role between demo sessions.
    user = User(
        id=gen_id(), email='ai-agent@system.demo', name='AI Compliance Agent',
        role='AI_AGENT', password_hash='SYSTEM_ROLE_NOT_A_HUMAN_LOGIN',
        email_verified=True, mobile_verified=True, verification_status='VERIFIED',
    )
    db.session.add(user)
    db.session.flush()
    return user


def _ensure_demo_workflows(reset=False):
    """Create/update the five presentation workflows using the existing ORM.

    The data lives in the existing Business/Application/Inspection/AuditLog
    tables, so refreshes and role changes keep a single source of truth.
    """
    _ensure_system_user()
    pharmacy = _ensure_pharmacy_type()
    inspectors = User.query.filter_by(role='OFFICER', is_active=True).all()
    demo_names = list(DEMO_PROFILES.keys())
    result = []
    for name, profile in DEMO_PROFILES.items():
        # Distribute demo inspections across LICENCE OFFICER desks (combined
        # officer/inspector role) so every desk has a real workload.
        inspector = inspectors[demo_names.index(name) % len(inspectors)] if inspectors else None
        business = Business.query.filter_by(name=name).first()
        if not business:
            # Profiles normally come from seed.py, but this supports an older
            # existing database without forcing a destructive global reset.
            owner = User.query.filter_by(email=profile['owner_email']).first() or User.query.filter_by(role='APPLICANT').first()
            if not owner:
                continue
            sector = 'RESTAURANT' if 'Restaurant' in name else ('MANUFACTURING' if 'Manufacturing' in name else ('RETAIL' if 'Retail' in profile['type'] else ('SERVICE' if 'Software' in profile['type'] else 'HEALTHCARE')))
            business = Business(
                id=gen_id(), owner_id=owner.id, name=name, owner_name=owner.name,
                business_type='RESTAURANT' if sector == 'RESTAURANT' else ('MANUFACTURING_UNIT' if sector == 'MANUFACTURING' else ('SERVICE_BUSINESS' if sector == 'SERVICE' else 'RETAIL_BUSINESS')),
                sector=sector, state='Demo State', district='Demo District', city='Demo City',
                address='Demonstration premises — not a real address', investment_amount=3500000,
                employee_count=22 if sector == 'RESTAURANT' else 12, size_category='SMALL',
                is_manufacturing=sector == 'MANUFACTURING', handles_food=sector == 'RESTAURANT',
                uses_hazardous=sector in ['MANUFACTURING', 'HEALTHCARE'],
                uses_heavy_machinery=sector == 'MANUFACTURING', has_physical_infra=True,
                env_approval_applicable=sector == 'MANUFACTURING', fire_risk='HIGH' if sector == 'MANUFACTURING' else 'MEDIUM',
            )
            db.session.add(business)
            db.session.flush()
        if reset or not business.status or business.status == 'ACTIVE':
            business.status = profile['state']

        for index, code in enumerate(profile['codes']):
            approval_type = pharmacy if code == 'PHARMACY_DEMO' else _type_by_code(code)
            if not approval_type:
                continue
            app = Application.query.filter_by(business_id=business.id, approval_type_id=approval_type.id).first()
            if not app:
                app = Application(
                    id=gen_id(), application_number=_application_number(), business_id=business.id,
                    approval_type_id=approval_type.id, department_id=approval_type.department_id,
                    applicant_id=business.owner_id, status=profile['statuses'][index],
                    submission_date=now() - timedelta(days=3),
                    sla_deadline=now() + timedelta(days=max(1, approval_type.sla_days or 10)),
                    notes='AI DEMO: simulated parallel departmental workflow.',
                )
                db.session.add(app)
                db.session.flush()
                db.session.add(ApplicationStatusHistory(
                    application_id=app.id, status=app.status,
                    changed_by_id=_actor().id if _actor() else None,
                    notes='SIMULATED AI analysis created this parallel workflow.',
                ))
                _add_audit(app, 'AI_DEMO_WORKFLOW_CREATED', f'{name}: {approval_type.name} routed by simulated rules.')
            # Applications that have progressed past the automatic-verification
            # stage (routed to an officer / awaiting or in inspection / under
            # correction) must carry a completed AI review so the officer can
            # legally sign off without re-running verification.
            if app.status in ('SUBMITTED', 'UNDER_REVIEW',
                              'SUBMITTED_TO_AUTHORITY', 'ASSIGNED_TO_OFFICER',
                              'DECISION_PENDING', 'INSPECTION_REQUIRED',
                              'INSPECTION_SCHEDULED', 'INSPECTION_COMPLETED',
                              'INSPECTION_PASSED', 'CORRECTION_REQUIRED'):
                app.ai_reviewed_at = app.ai_reviewed_at or now()
            elif reset:
                app.status = profile['statuses'][index]
                app.sla_deadline = now() + timedelta(days=max(1, approval_type.sla_days or 10))
                app.correction_notes = None
                # Restore a clean interactive sample: the current draft
                # document/certificate state is removed, while AuditLog rows
                # stay retained as a governed demonstration record.
                for renewal in Renewal.query.filter_by(application_id=app.id).all():
                    db.session.delete(renewal)
                for certificate in Certificate.query.filter_by(application_id=app.id).all():
                    db.session.delete(certificate)
                for document in Document.query.filter_by(application_id=app.id).all():
                    db.session.delete(document)

            if approval_type.requires_inspection and code in ['FIRE_NOC', 'FACTORY_LIC', 'PHARMACY_DEMO']:
                inspection = Inspection.query.filter_by(application_id=app.id).first()
                desired = 'SCHEDULED' if app.status == 'INSPECTION_SCHEDULED' else ('ASSIGNED' if app.status == 'INSPECTION_REQUIRED' else None)
                # COMBINED ROLE: the same licence officer that reviews the app
                # also conducts its inspection. Assign the inspection to the
                # application's deterministic owning officer (licence-driven).
                owner = find_best_officer(app.approval_type_id, None)
                inspection_owner_id = owner.user_id if owner else None
                if desired and not inspection:
                    inspection = Inspection(
                        id=gen_id(), application_id=app.id,
                        inspector_id=inspection_owner_id,
                        assigned_by_id=_actor().id if _actor() else None,
                        status=desired, scheduled_date=now() + timedelta(days=1) if desired == 'SCHEDULED' else None,
                    )
                    db.session.add(inspection)
                elif desired and reset:
                    inspection.status = desired
                    inspection.inspector_id = inspection_owner_id
                    inspection.scheduled_date = now() + timedelta(days=1) if desired == 'SCHEDULED' else None
                    inspection.completed_date = None
                    inspection.report_submitted_at = None
                    inspection.overall_result = None
                    inspection.recommendation = None
                    inspection.remarks = None
            _seed_demo_documents(app)
        _backfill_completed_checklist(business)
        result.append(business)
    db.session.commit()
    return result


def _backfill_completed_checklist(business):
    """Ensure each demo business holds an application for EVERY mandatory
    approval the rule engine matches for its profile, so the AI decision
    engine's completeness check reflects the full journey (earlier approvals
    already granted) instead of a partial snapshot of the demo.
    Missing ones are created as previously-APPROVED applications.
    """
    if not business:
        return
    present = {a.approval_type.code for a in business.applications if a.approval_type}
    matched = ai_decision_service.evaluate_rules(business)
    for entry in matched:
        at = entry['approval_type']
        if not entry['mandatory'] or at.code in present:
            continue
        app = Application(
            id=gen_id(), application_number=_application_number(), business_id=business.id,
            approval_type_id=at.id, department_id=at.department_id,
            applicant_id=business.owner_id, status='APPROVED',
            submission_date=now() - timedelta(days=30),
            decision_date=now() - timedelta(days=12),
            sla_deadline=now() - timedelta(days=18),
            notes='Prior approval already granted — reused as an established compliance credential.',
        )
        db.session.add(app)
        db.session.flush()
        db.session.add(ApplicationStatusHistory(
            application_id=app.id, status='APPROVED',
            changed_by_id=_actor().id if _actor() else None,
            notes='Prior approved credential recognised by the AI Compliance Agent.',
        ))
        _add_audit(app, 'AI_CREDENTIAL_REUSED',
                   f'{business.name}: {at.name} recognised as an already-approved credential.')
    return


def _seed_demo_documents(app):
    """Give demo applications representative verified documents so the AI
    decision engine can demonstrate varied, honest outcomes per workflow.
    Idempotent: skips applications that already hold documents.
    """
    if Document.query.filter_by(application_id=app.id).first():
        return
    if app.status not in ['SUBMITTED', 'UNDER_REVIEW', 'INSPECTION_REQUIRED',
                          'INSPECTION_SCHEDULED', 'INSPECTION_COMPLETED',
                          'CORRECTION_REQUIRED', 'DOCUMENT_VALIDATION']:
        return
    approval_type = app.approval_type
    if not approval_type:
        return
    reqs = DocumentRequirement.query.filter_by(approval_type_id=approval_type.id).all()
    if not reqs:
        return
    uploaded_at = now() - timedelta(days=2)
    for i, req in enumerate(reqs):
        verified = Document(
            id=gen_id(), application_id=app.id, business_id=app.business_id,
            requirement_id=req.id, uploader_id=business.owner_id if (business := app.business) else None,
            filename=f'demo_{req.code.lower()}_{i}.pdf',
            original_filename=f'{req.name}.pdf',
            doc_type=req.code, mime_type='application/pdf', file_size=240000 + i * 12000,
            document_version=1,
            status='VERIFIED',
            verification_status='REJECTED' if (i == len(reqs) - 1 and app.status == 'CORRECTION_REQUIRED') else 'VERIFIED',
            verification_notes=('SIMULATED AI check: demo document re-validated after correction (96% confidence). Compiled for SIH demonstration.'
                                if app.status == 'CORRECTION_REQUIRED' else
                                'SIMULATED AI verification for the SIH demo. Compiled, not a real government document.'),
            verified_by_id=_ensure_system_user().id,
            uploaded_at=uploaded_at,
            verified_at=now() - timedelta(hours=6),
        )
        db.session.add(verified)
    db.session.add(AuditLog(
        application_id=app.id,
        user_id=_actor().id if _actor() else None,
        action='AI_DOCUMENT_VALIDATED',
        details=f'Simulated AI validated {len(reqs)} document(s) for {app.business.name}. Always shows the decision reasoning openly.',
    ))


def _workflow_payload(business):
    profile = DEMO_PROFILES[business.name]
    applications = Application.query.filter_by(business_id=business.id).all()
    # Requirements come from the business's ACTUAL persisted applications so the
    # AI workflow, the applicant's business detail, and the inspector/admin views
    # all share the same single source of truth (no drift between sources).
    requirements = []
    for app in applications:
        approval = app.approval_type
        if not approval:
            continue
        requirements.append({
            'application_id': app.id, 'code': approval.code, 'name': approval.name,
            'department': app.department.name if app.department else 'Demo Department',
            'status': app.status, 'why_required': approval.why_required,
            'estimated_days': approval.estimated_days, 'sla_days': approval.sla_days,
            'inspection_required': approval.requires_inspection,
            'documents': [r.to_dict() for r in approval.document_requirements],
        })
    inspection = next((i for app in applications for i in app.inspections if i.status != 'COMPLETED'), None)
    audit = AuditLog.query.filter(AuditLog.application_id.in_([a.id for a in applications] or ['-'])).order_by(AuditLog.created_at.desc()).limit(20).all()
    # A reset preserves audit evidence but restores the guided correction state.
    revalidated = business.status != 'CORRECTION_REQUIRED' and any(log.action == 'AI_DOCUMENT_REVALIDATED' for log in audit)
    activity = [
        {'time': '10:42 AM', 'action': f'AI identified business category: {profile["type"]}', 'kind': 'analysis'},
        {'time': '10:43 AM', 'action': f'AI generated a customised checklist with {len(requirements)} requirements', 'kind': 'checklist'},
        {'time': '10:44 AM', 'action': f'AI routed {len({r["department"] for r in requirements})} departments to run in parallel', 'kind': 'routing'},
        {'time': '10:45 AM', 'action': profile['why'], 'kind': 'decision'},
    ]
    if business.name == 'Urban Spice Restaurant':
        activity += [
            {'time': '10:47 AM', 'action': 'Address proof mismatch detected (72% confidence); correction request issued.', 'kind': 'alert'},
            {'time': '10:52 AM', 'action': 'Corrected address proof revalidated (96% confidence).' if revalidated else 'Awaiting corrected address proof for revalidation.', 'kind': 'validation'},
            {'time': '10:55 AM', 'action': 'Fire inspection task created and applicant notified.', 'kind': 'inspection'},
        ]
    activity += [
        {'time': log.created_at.strftime('%I:%M %p') if log.created_at else 'Now', 'action': log.details or log.action.replace('_', ' ').title(), 'kind': 'audit'} for log in reversed(audit[:8])
    ]
    return {
        'business': business.to_dict(), 'profile': profile,
        'state': business.status or profile['state'], 'requirements': requirements,
        'risk': {'score': profile['risk_score'], 'level': profile['risk'], 'recommendation': 'Eligible for streamlined processing.' if profile['risk'] == 'LOW' else ('Enhanced verification and an accountable admin review are recommended.' if profile['risk'] == 'HIGH' else 'Standard verification with enhanced document scrutiny is recommended.')},
        'documents': [
            {'name': 'PAN Card', 'mandatory': True, 'format': 'PDF, JPG or PNG', 'max_size': '5 MB', 'status': 'UNDER_OFFICER_REVIEW', 'confidence': 98, 'reason': 'Business identity verification'},
            {'name': 'Address Proof', 'mandatory': True, 'format': 'PDF, JPG or PNG', 'max_size': '5 MB', 'status': 'UNDER_OFFICER_REVIEW' if revalidated else ('RESUBMISSION_REQUIRED' if business.name == 'Urban Spice Restaurant' else 'UNDER_OFFICER_REVIEW'), 'confidence': 96 if revalidated else (72 if business.name == 'Urban Spice Restaurant' else 95), 'reason': 'Premises verification'},
            {'name': 'Business Registration', 'mandatory': True, 'format': 'PDF, JPG or PNG', 'max_size': '5 MB', 'status': 'UNDER_OFFICER_REVIEW', 'confidence': 97, 'reason': 'Verified once and reusable across applications'},
        ],
        'inspection': inspection.to_dict() if inspection else None,
        'activity': activity,
        'verified_profile': {'name': business.name, 'owner': business.owner_name, 'address': business.address, 'business_type': profile['type'], 'reuse_message': 'Verified once • automatically reused for future applications and renewal.'},
        'schemes': _scheme_matches(business),
    }


def _scheme_matches(business):
    generic = {
        'Restaurant': [('Small Business Support', 'Small customer-facing business profile', 'DEMO SCHEME DATA'), ('Digital Adoption Incentive', 'Digital workflow and payment adoption', 'DEMO SCHEME DATA')],
        'Manufacturing': [('Manufacturing Efficiency Support', 'Small manufacturing profile', 'DEMO SCHEME DATA'), ('Green Operations Incentive', 'Environmental documentation workflow', 'DEMO SCHEME DATA')],
        'Retail': [('Small Business Support', 'Small retail profile', 'DEMO SCHEME DATA')],
        'IT / Software': [('Digital Adoption Incentive', 'Technology services profile', 'DEMO SCHEME DATA'), ('Startup Support', 'Low-complexity service business', 'DEMO SCHEME DATA')],
        'Pharmacy': [('Healthcare Retail Modernisation', 'Medical-retail profile', 'DEMO SCHEME DATA')],
    }
    profile = DEMO_PROFILES.get(business.name, {})
    key = 'Manufacturing' if 'Manufacturing' in profile.get('type', '') else ('IT / Software' if 'Software' in profile.get('type', '') else ('Pharmacy' if 'Pharmacy' in profile.get('type', '') else ('Restaurant' if 'Restaurant' in profile.get('type', '') else 'Retail')))
    return [{'name': item[0], 'reason': item[1], 'label': item[2], 'status': 'Potentially eligible'} for item in generic.get(key, [])]


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def _automation_metrics():
    """Compute governance-style metrics from actual persisted data.

    No hardcoded percentages: automation rate reflects how many active
    applications were actually reviewed by the AI decision engine; SLA
    compliance and processing time are derived from persisted dates.
    """
    active = Application.query.filter(
        Application.status.in_(['SUBMITTED', 'UNDER_REVIEW', 'DOCUMENT_VALIDATION',
                                'INSPECTION_REQUIRED', 'INSPECTION_SCHEDULED',
                                'INSPECTION_COMPLETED', 'DECISION_PENDING',
                                'APPROVED', 'REJECTED'])
    ).all()

    reviewed = sum(1 for a in active if a.ai_reviewed_at is not None)
    automation_rate = round(reviewed / len(active) * 100) if active else 0

    est_days, act_days = [], []
    for a in active:
        if a.status in ('APPROVED', 'REJECTED') and a.submission_date and a.decision_date:
            act = max(0, (_utc(a.decision_date) - _utc(a.submission_date)).total_seconds() / 86400)
            act_days.append(act)
            est = a.approval_type.estimated_days if a.approval_type and a.approval_type.estimated_days else 10
            est_days.append(est)
    avg_processing_days = round(sum(act_days) / len(act_days), 1) if act_days else 0
    if act_days and est_days:
        ratio = sum(act_days) / sum(est_days)
        time_saved = max(0, min(95, round((1 - ratio) * 100)))
    else:
        time_saved = 0

    compliant, assessed = 0, 0
    for a in active:
        if not a.sla_deadline:
            continue
        assessed += 1
        deadline = _utc(a.sla_deadline)
        if a.status in ('APPROVED', 'REJECTED'):
            if a.decision_date and _utc(a.decision_date) <= deadline:
                compliant += 1
        elif now() <= deadline:
            compliant += 1
    sla_compliance = round(compliant / assessed * 100) if assessed else 0

    return {
        'automation_rate': automation_rate,
        'avg_processing_days': avg_processing_days,
        'time_saved_pct': time_saved,
        'sla_compliance': sla_compliance,
        'reviewed_applications': reviewed,
    }

@ai_agent_bp.route('/dashboard', methods=['GET'])
@jwt_required()
def ai_dashboard():
    """AI Agent dashboard statistics and activity stream."""
    total_apps = Application.query.count()
    metrics = _automation_metrics()
    auto_processed = metrics['reviewed_applications']
    automation_rate = metrics['automation_rate']
    docs_validated = Document.query.filter_by(verification_status='VERIFIED').count()
    inspections = Inspection.query.count()
    sla_alerts = Application.query.filter(
        Application.sla_deadline < now(),
        Application.status.notin_(['APPROVED', 'REJECTED'])
    ).count()
    exceptions = Application.query.filter(
        Application.status == 'CORRECTION_REQUIRED'
    ).count()
    ai_reviews = metrics['reviewed_applications']
    pending_decisions = Application.query.filter(
        Application.status.in_(['SUBMITTED', 'UNDER_REVIEW', 'DOCUMENT_VALIDATION']),
        Application.ai_reviewed_at.is_(None)
    ).count()
    depts_coordinated = len({a.department.code for a in Application.query.all()
                             if a.status != 'DRAFT' and a.department and a.department.code})

    # Build a real, persisted activity stream from AuditLog.
    ai_actions = []
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(14).all()
    for log in logs:
        ai_actions.append({
            'time': log.created_at.strftime('%I:%M %p') if log.created_at else 'Now',
            'action': log.details or log.action.replace('_', ' ').title(),
            'type': 'audit', 'icon': '🤖', 'color': '#6366f1',
        })

    return jsonify({
        'stats': {
            'active_applications': total_apps,
            'auto_processed': auto_processed,
            'automation_rate': automation_rate,
            'docs_validated': docs_validated,
            'ai_reviews': ai_reviews,
            'pending_decisions': pending_decisions,
            'depts_coordinated': depts_coordinated,
            'inspections_scheduled': inspections,
            'sla_alerts': sla_alerts,
            'exceptions': exceptions,
            'avg_processing_days': metrics['avg_processing_days'],
            'time_saved_pct': metrics['time_saved_pct'],
        },
        'activity': ai_actions,
    }), 200


@ai_agent_bp.route('/businesses', methods=['GET'])
@jwt_required()
def ai_businesses():
    """Get all businesses with AI-computed stats for the demo selector."""
    businesses = Business.query.all()
    result = []

    SECTOR_TO_TYPE = {
        'RESTAURANT': ('Restaurant', '🍽️', 'LOW / MEDIUM', '#d97706'),
        'FOOD_SERVICE': ('Restaurant', '🍽️', 'LOW / MEDIUM', '#d97706'),
        'MANUFACTURING': ('Manufacturing', '🏭', 'MEDIUM / HIGH', '#dc2626'),
        'FOOD_PROCESSING': ('Manufacturing', '🏭', 'MEDIUM / HIGH', '#dc2626'),
        'RETAIL': ('Retail', '🛒', 'LOW', '#16a34a'),
        'WHOLESALE': ('Retail', '🛒', 'LOW', '#16a34a'),
        'SERVICE': ('IT / Software', '💻', 'LOW', '#16a34a'),
        'ELECTRONICS': ('Retail', '🛒', 'LOW', '#16a34a'),
        'HEALTHCARE': ('Pharmacy', '💊', 'MEDIUM / HIGH', '#d97706'),
        'CONSTRUCTION': ('Construction', '🏗️', 'HIGH', '#dc2626'),
    }

    for b in businesses:
        apps = Application.query.filter_by(business_id=b.id).all()
        total = len(apps)
        approved = sum(1 for a in apps if a.status == 'APPROVED')
        pct = int((approved / total) * 100) if total > 0 else 0
        has_insp_sched = any(a.status == 'INSPECTION_SCHEDULED' for a in apps)
        has_insp_comp = any(a.status == 'INSPECTION_COMPLETED' for a in apps)
        has_insp_req = any(a.status == 'INSPECTION_REQUIRED' for a in apps)
        inspection_status = 'Completed' if has_insp_comp else ('Scheduled' if has_insp_sched else ('Required' if has_insp_req else 'Not Required'))

        sector_info = SECTOR_TO_TYPE.get(b.sector, ('Business', '🏢', 'LOW', '#64748b'))

        result.append({
            'id': b.id,
            'name': b.name,
            'sector': b.sector,
            'business_type': b.business_type,
            'city': b.city,
            'state': b.state,
            'display_type': sector_info[0],
            'icon': sector_info[1],
            'risk': sector_info[2],
            'risk_color': sector_info[3],
            'total_requirements': total,
            'approved': approved,
            'progress_pct': pct,
            'inspection_status': inspection_status,
            'fire_risk': b.fire_risk,
            'employee_count': b.employee_count,
        })

    return jsonify({'businesses': result}), 200


@ai_agent_bp.route('/risk/<business_id>', methods=['GET'])
@jwt_required()
def get_risk(business_id):
    """Compute AI risk score for a business (deterministic demo logic)."""
    business = Business.query.get_or_404(business_id)

    score = 0
    factors = []

    if business.is_manufacturing:
        score += 30
        factors.append({'factor': 'Manufacturing operations', 'impact': '+30', 'level': 'high'})
    if business.uses_hazardous:
        score += 25
        factors.append({'factor': 'Hazardous materials usage', 'impact': '+25', 'level': 'high'})
    if business.handles_food:
        score += 15
        factors.append({'factor': 'Food handling operations', 'impact': '+15', 'level': 'medium'})
    if business.env_approval_applicable:
        score += 20
        factors.append({'factor': 'Environmental impact applicable', 'impact': '+20', 'level': 'medium'})
    if business.fire_risk == 'HIGH':
        score += 20
        factors.append({'factor': 'High fire risk premises', 'impact': '+20', 'level': 'high'})
    elif business.fire_risk == 'MEDIUM':
        score += 10
        factors.append({'factor': 'Medium fire risk premises', 'impact': '+10', 'level': 'medium'})
    if business.employee_count and business.employee_count > 50:
        score += 10
        factors.append({'factor': f'Large workforce ({business.employee_count} employees)', 'impact': '+10', 'level': 'medium'})
    elif business.employee_count and business.employee_count > 10:
        score += 5
        factors.append({'factor': f'Moderate workforce ({business.employee_count} employees)', 'impact': '+5', 'level': 'low'})

    score = min(score, 100)

    if score < 30:
        level, color, rec, workflow = 'LOW', '#16a34a', 'Eligible for streamlined automated processing. Standard document verification applies.', 'STREAMLINED'
    elif score < 60:
        level, color, rec, workflow = 'MEDIUM', '#d97706', 'Standard verification with enhanced document scrutiny recommended.', 'STANDARD'
    else:
        level, color, rec, workflow = 'HIGH', '#dc2626', 'Enhanced verification required. Physical inspection mandatory. Admin review recommended.', 'ENHANCED'

    return jsonify({
        'risk': {
            'score': score, 'level': level, 'color': color,
            'recommendation': rec, 'workflow': workflow, 'factors': factors,
        }
    }), 200


@ai_agent_bp.route('/demo-session', methods=['POST'])
def demo_session():
    """Enter the system role without exposing it as a human-user login."""
    agent = _ensure_system_user()
    db.session.commit()
    token = create_access_token(identity=agent.id)
    return jsonify({
        'token': token,
        'user': agent.to_dict(),
        'notice': 'AI DEMO — this is a simulated system role, not a human account.',
    }), 200


@ai_agent_bp.route('/demo-workflows', methods=['GET'])
@jwt_required()
def demo_workflows():
    businesses = _ensure_demo_workflows()
    cards = []
    for business in businesses:
        profile = DEMO_PROFILES[business.name]
        apps = Application.query.filter_by(business_id=business.id).all()
        inspections = [inspection for app in apps for inspection in app.inspections]
        inspection = next((i for i in inspections if i.status != 'COMPLETED'), None)
        cards.append({
            'id': business.id, 'name': business.name, 'type': profile['type'],
            'icon': profile['icon'], 'risk': profile['risk'],
            'requirements': len([app for app in apps if app.approval_type]),
            'progress': 100 if business.status in ['APPROVED', 'RENEWED'] else profile['progress'],
            'state': business.status or profile['state'],
            'inspection_status': inspection.status.replace('_', ' ').title() if inspection else profile['inspection'],
        })
    return jsonify({'businesses': cards, 'label': 'DEMO REGULATORY RULES — simulated for SIH presentation'}), 200


@ai_agent_bp.route('/workflow/<business_id>', methods=['GET'])
@jwt_required()
def workflow(business_id):
    _ensure_demo_workflows()
    business = Business.query.get_or_404(business_id)
    if business.name not in DEMO_PROFILES:
        return jsonify({'error': 'This is not one of the five SIH demonstration workflows.'}), 404
    return jsonify({'workflow': _workflow_payload(business)}), 200


@ai_agent_bp.route('/workflow/<business_id>/revalidate', methods=['POST'])
@jwt_required()
def revalidate_document(business_id):
    _ensure_demo_workflows()
    business = Business.query.get_or_404(business_id)
    if business.name != 'Urban Spice Restaurant':
        return jsonify({'error': 'The guided correction demo is available for Urban Spice Restaurant.'}), 400
    actor = get_current_user()
    apps = Application.query.filter_by(business_id=business.id).all()
    anchor = next((app for app in apps if app.approval_type and app.approval_type.code == 'FIRE_NOC'), apps[0] if apps else None)
    business.status = 'PARALLEL_PROCESSING'
    if anchor:
        _add_audit(anchor, 'AI_DOCUMENT_REVALIDATED', 'SIMULATED AI: corrected Address Proof passed consistency checks at 96% confidence.', actor)
        _add_audit(anchor, 'AI_PARALLEL_WORKFLOW_STARTED', 'SIMULATED AI: routine Trade, Food, Pollution and Labour workflows continue in parallel.', actor)
    _add_notification(business.owner_id, 'Document revalidated', 'AI DEMO: your corrected address proof passed pre-validation and parallel workflows have resumed.', 'SUCCESS', anchor.id if anchor else None)
    db.session.commit()
    return jsonify({'workflow': _workflow_payload(business), 'message': 'Corrected document revalidated at 96% confidence.'}), 200


@ai_agent_bp.route('/inspection/<business_id>/start', methods=['POST'])
@jwt_required()
def start_demo_inspection(business_id):
    user = get_current_user()
    if user.role not in ['OFFICER', 'ADMIN']:
        return jsonify({'error': 'Inspector or Admin access required'}), 403
    business = Business.query.get_or_404(business_id)
    apps = Application.query.filter_by(business_id=business.id).all()
    inspection = next((inspection for app in apps for inspection in app.inspections if inspection.status in ['ASSIGNED', 'SCHEDULED']), None)
    if not inspection:
        return jsonify({'error': 'No pending simulated inspection for this business.'}), 400
    inspection.status = 'STARTED'
    app = Application.query.get(inspection.application_id)
    if app:
        app.status = 'INSPECTION_REQUIRED'
        _add_audit(app, 'INSPECTION_STARTED', 'Inspector started a physical-verification task.', user)
    db.session.commit()
    return jsonify({'inspection': inspection.to_dict()}), 200


@ai_agent_bp.route('/inspection/<business_id>/complete', methods=['POST'])
@jwt_required()
def complete_demo_inspection(business_id):
    user = get_current_user()
    if user.role not in ['OFFICER', 'ADMIN']:
        return jsonify({'error': 'Inspector or Admin access required'}), 403
    business = Business.query.get_or_404(business_id)
    result = (request.get_json(silent=True) or {}).get('result', 'PASS').upper()
    apps = Application.query.filter_by(business_id=business.id).all()
    inspection = next((inspection for app in apps for inspection in app.inspections if inspection.status != 'COMPLETED'), None)
    if not inspection:
        return jsonify({'error': 'No simulated inspection task is open.'}), 400
    app = Application.query.get(inspection.application_id)
    inspection.status = 'COMPLETED'
    inspection.completed_date = now()
    inspection.report_submitted_at = now()
    inspection.overall_result = result
    inspection.recommendation = 'APPROVE' if result == 'PASS' else ('CORRECTION' if result == 'NEEDS_REVIEW' else 'REJECT')
    inspection.remarks = 'SIMULATED field verification completed for SIH demonstration.'
    if app:
        app.status = 'APPROVED' if result == 'PASS' else ('EXCEPTION' if result == 'NEEDS_REVIEW' else 'CORRECTION_REQUIRED')
        _add_audit(app, 'INSPECTION_RESULT_RECEIVED', f'Inspector submitted {result}; AI updated the coordinated workflow.', user)
    if result == 'PASS' and business.name == 'Urban Spice Restaurant':
        business.status = 'APPROVAL_READY'
        for item in apps:
            if item.status not in ['APPROVED', 'REJECTED']:
                item.status = 'APPROVED'
                _add_audit(item, 'AI_ROUTINE_DEPARTMENT_COMPLETED', 'SIMULATED AI marked the parallel departmental requirement complete.', user)
    elif result == 'NEEDS_REVIEW':
        business.status = 'EXCEPTION'
    else:
        business.status = 'CORRECTION_REQUIRED'
    _add_notification(business.owner_id, 'Inspection completed', f'AI DEMO: the {business.name} inspection result is {result}.', 'SUCCESS' if result == 'PASS' else 'WARNING', app.id if app else None)
    db.session.commit()
    return jsonify({'workflow': _workflow_payload(business)}), 200


@ai_agent_bp.route('/inspection/<inspection_id>/assist', methods=['POST'])
@jwt_required()
def ai_inspection_assistant(inspection_id):
    """Simulated AI Inspection Assistant: reviews the inspector's checklist
    entries and remarks and returns a transparent recommendation the inspector
    can adopt before finalising the report. Deterministic demo logic only.
    """
    user = get_current_user()
    if user.role not in ['OFFICER', 'ADMIN']:
        return jsonify({'error': 'Inspector or Admin access required'}), 403
    inspection = Inspection.query.get_or_404(inspection_id)
    data = request.get_json(silent=True) or {}
    checks = data.get('checklist_data') or []
    remarks = (data.get('remarks') or '').strip()

    if isinstance(checks, str):
        try:
            checks = json.loads(checks)
        except Exception:
            checks = []
    total = len(checks)
    checked = sum(1 for c in checks if isinstance(c, dict) and c.get('checked'))
    fail_count = sum(1 for c in checks if isinstance(c, dict) and c.get('checked') is False and (c.get('remark') or '').strip())

    verified = next((c for c in checks if isinstance(c, dict) and c.get('remark')), None)
    notes = verified.get('remark') if verified else ''
    high_risk_flag = 'Hazardous' in remarks or 'violation' in remarks.lower() or 'escal' in remarks.lower()

    if total > 0:
        completion = round(checked / total * 100)
    else:
        completion = 0

    if completion >= 80 and not high_risk_flag:
        recommendation, confidence, color = 'APPROVE', 88 + completion // 10, '#16a34a'
        summary = f'All {checked}/{total} checklist items cleared. Simulated AI recommends {recommendation}.'
    elif high_risk_flag or fail_count > total // 3 and completion < 80:
        recommendation, confidence, color = 'REJECT', 90, '#dc2626'
        summary = f'{fail_count} checklist item(s) failed and the remarks suggest serious non-compliance. Simulated AI recommends {recommendation}.'
    else:
        recommendation, confidence, color = 'CORRECTION', 70, '#d97706'
        summary = f'{checked}/{total} items cleared, but {total - checked} remain unresolved. Simulated AI recommends corrective review rather than approval.'

    if notes:
        summary += f' Key observation: {notes[:120]}.'

    _add_audit(Application.query.get(inspection.application_id), 'AI_INSPECTION_ASSIST', f'Inspector used the simulated AI Inspection Assistant (confidence {confidence}%, recommendation {recommendation}).', user)
    db.session.commit()
    return jsonify({
        'assistance': {
            'recommendation': recommendation, 'confidence': confidence, 'color': color,
            'summary': summary, 'completion': completion,
            'disclaimer': 'SIMULATED AI guidance for the SIH demo — the inspector makes the final accountable decision.',
        }
    }), 200


@ai_agent_bp.route('/workflow/<business_id>/approve', methods=['POST'])
@jwt_required()
def approve_demo_workflow(business_id):
    user = get_current_user()
    if user.role != 'ADMIN':
        return jsonify({'error': 'An accountable Admin review is required for the final demo decision.'}), 403
    business = Business.query.get_or_404(business_id)
    if business.status != 'APPROVAL_READY':
        return jsonify({'error': 'The workflow is not yet approval ready.'}), 400
    apps = Application.query.filter_by(business_id=business.id).all()
    app = next((item for item in apps if item.approval_type and item.approval_type.code == 'FIRE_NOC'), apps[0] if apps else None)
    if not app:
        return jsonify({'error': 'No approval workflow found.'}), 400
    app.status = 'APPROVED'
    app.decision_date = now()
    certificate = Certificate.query.filter_by(application_id=app.id).first()
    if not certificate:
        certificate = Certificate(
            id=gen_id(), application_id=app.id,
            certificate_number=f'DEMO-NIR-{datetime.now().year}-{uuid.uuid4().hex[:6].upper()}',
            business_name=business.name, applicant_name=business.owner_name,
            approval_type_name='Unified Approval Readiness (DEMO)',
            department_name='NIRMAN simulated coordinated workflow', issue_date=now(),
            valid_until=now() + timedelta(days=335),
            verification_id=f'DEMO-VID-{uuid.uuid4().hex[:10].upper()}',
            qr_data='DEMO ONLY — NOT A GOVERNMENT CERTIFICATE', is_prototype=True,
        )
        db.session.add(certificate)
        db.session.flush()
        db.session.add(Renewal(certificate_id=certificate.id, application_id=app.id, expiry_date=certificate.valid_until, status='ACTIVE'))
    business.status = 'APPROVED'
    _add_audit(app, 'ADMIN_ACCEPTED_AI_RECOMMENDATION', 'Accountable demo review accepted the AI recommendation after all mandatory conditions were met.', user)
    _add_notification(business.owner_id, 'Approval ready — demo certificate issued', 'All mandatory demo checks are complete. A prototype certificate is now available; renewal monitoring has started.', 'SUCCESS', app.id)
    db.session.commit()
    return jsonify({'workflow': _workflow_payload(business), 'certificate': certificate.to_dict()}), 200


@ai_agent_bp.route('/governance', methods=['GET'])
@jwt_required()
def governance():
    _ensure_demo_workflows()
    items = []
    for name, profile in DEMO_PROFILES.items():
        business = Business.query.filter_by(name=name).first()
        if not business:
            continue
        if profile['risk'] == 'HIGH' or business.status in ['EXCEPTION', 'CORRECTION_REQUIRED']:
            reason = 'High-risk profile requires accountable review' if profile['risk'] == 'HIGH' else 'Document inconsistency / correction workflow'
            items.append({'business_id': business.id, 'application': name, 'reason': reason, 'risk': profile['risk'], 'recommendation': 'Accept enhanced verification' if profile['risk'] == 'HIGH' else 'Request corrected information', 'state': business.status})
    return jsonify({
        'exceptions': items,
        'delay_analysis': _delay_analysis(items),
        'metrics': _governance_metrics(items),
    }), 200


def _delay_analysis(items):
    """AI delay insight derived from actual inspection/application data."""
    fire = Department.query.filter_by(code='FIRE_SERVICE').first() or Department.query.filter(
        Department.name.ilike('%fire%')
    ).first()
    fire_apps = [a for a in Application.query.filter_by(department_id=fire.id).all()] if fire else []
    if fire_apps:
        days = [max(0, (_utc(a.sla_deadline) - _utc(a.created_at)).days) for a in fire_apps if a.sla_deadline]
        avg = round(sum(days) / len(days), 1) if days else 0
        breached = sum(1 for a in fire_apps if a.sla_deadline and a.status not in ['APPROVED', 'REJECTED'] and _utc(a.sla_deadline) < now())
        rate = round(breached / max(1, len(fire_apps)) * 100) if fire_apps else 0
    else:
        avg, rate = 0, 0
    return {
        'department': 'Fire Department',
        'average_processing_days': avg,
        'sla_days': fire.sla_days if fire else 3,
        'breach_rate': rate,
        'insight': 'SIMULATED AI insight: fire-inspection scheduling is the largest contributor to approval delay in this demo dataset.',
    }


def _governance_metrics(items):
    metrics = _automation_metrics()
    return {
        'automation_rate': metrics['automation_rate'],
        'sla_compliance': metrics['sla_compliance'],
        'time_saved': metrics['time_saved_pct'],
        'incomplete_applications': len([item for item in items if item['state'] == 'CORRECTION_REQUIRED']),
    }


@ai_agent_bp.route('/exception/<business_id>/action', methods=['POST'])
@jwt_required()
def exception_action(business_id):
    user = get_current_user()
    if user.role != 'ADMIN':
        return jsonify({'error': 'Admin access required'}), 403
    data = request.get_json(silent=True) or {}
    action = data.get('action', 'REVIEW').upper()
    business = Business.query.get_or_404(business_id)
    apps = Application.query.filter_by(business_id=business.id).all()
    anchor = apps[0] if apps else None
    state_map = {'ACCEPT': 'AI_REVIEW', 'REJECT': 'CORRECTION_REQUIRED', 'REQUEST_INFO': 'CORRECTION_REQUIRED', 'OVERRIDE': 'APPROVAL_READY', 'ESCALATE': 'EXCEPTION'}
    business.status = state_map.get(action, business.status)
    _add_audit(anchor, f'ADMIN_EXCEPTION_{action}', f'Admin action: {action}. {data.get("notes", "No additional notes.")}', user)
    _add_notification(business.owner_id, 'Exception review updated', f'Admin action recorded: {action.replace("_", " ")}.', 'INFO', anchor.id if anchor else None)
    db.session.commit()
    return jsonify({'message': 'Exception action recorded in the audit trail.', 'state': business.status}), 200


@ai_agent_bp.route('/demo-reset', methods=['POST'])
@jwt_required()
def reset_demo_workflows():
    user = get_current_user()
    if user.role != 'ADMIN':
        return jsonify({'error': 'Admin access required'}), 403
    _ensure_demo_workflows(reset=True)
    return jsonify({'message': 'The five sample businesses and their simulated workflows have been restored.'}), 200


@ai_agent_bp.route('/application/<app_id>/decision', methods=['GET'])
@jwt_required()
def application_decision(app_id):
    """AI decision panel for a single application.

    Runs the deterministic decision engine (which may optionally consult the
    local Ollama model purely for explanation wording) and returns a complete,
    transparent breakdown for the UI. Does not mutate the application.
    """
    app = Application.query.get_or_404(app_id)
    assessment = ai_decision_service.assess_application(app)
    return jsonify({'assessment': assessment, 'application': app.to_dict(include_details=True)}), 200


@ai_agent_bp.route('/application/<app_id>/review', methods=['POST'])
@jwt_required()
def run_application_review(app_id):
    """Persist the AI review for a single application (audit-logged), then
    advance the coordinated workflow through the shared decision engine:
    APPROVE-worthy inspection apps move to a physical inspection; others move
    to the Admin decision gate."""
    user = get_current_user()
    app = Application.query.get_or_404(app_id)
    assessment = ai_decision_service.review_and_advance(app, user)
    db.session.commit()
    return jsonify({'assessment': assessment}), 200


@ai_agent_bp.route('/queue', methods=['GET'])
@jwt_required()
def ai_queue():
    """Applications awaiting (or already processed by) AI review."""
    pending = Application.query.filter(
        Application.status.in_(['SUBMITTED', 'UNDER_REVIEW', 'DOCUMENT_VALIDATION'])
    ).order_by(Application.submission_date.asc()).all()
    rows = []
    for app in pending:
        try:
            assessment = ai_decision_service.assess_application(app, enrich=False)
            rows.append({
                'id': app.id, 'application_number': app.application_number,
                'business': app.business.name if app.business else None,
                'approval_type': app.approval_type.name if app.approval_type else None,
                'status': app.status,
                'risk': assessment['risk'],
                'decision': assessment['decision'],
                'confidence': assessment['confidence'],
                'reason': assessment['reason'],
            })
        except Exception:
            continue
    return jsonify({'queue': rows}), 200

"""Idempotent seeding of the SINGLE Licence Officer / Inspector action demos.

This seeds a small, controlled set of demo applications (owned by the existing
demo applicant) that exercise every action a Licence Officer / Inspector can
take: Review, Request Correction, Approve for Inspection, Schedule, Open
Inspection, final approval and certificate generation.

Design rules honoured here:
  * There is exactly ONE officer account (Arjun Singh, inspector@demo.com).
  * Every demo application is owned by the designated demo applicant
    (applicant@demo.com) and assigned to Arjun Singh via application_assignments
    — they are never surfaced to newly registered applicants, whose own data is
    filtered by owner_id.
  * The seed is idempotent: running it repeatedly never creates duplicates.
  * All counts come from SQLite; nothing is hard-coded in the UI.
"""
from .. import db
from ..models import (
    Application, ApplicationAssignment, ApplicationStatusHistory, AuditLog,
    ApprovalType, Business, Document, DocumentRequirement, Inspection,
    InspectionEvidence, Notification, User, gen_id, now, Certificate,
)
from datetime import timedelta

# Email of the designated demo applicant who owns all demo businesses.
DEMO_APPLICANT_EMAIL = 'applicant@demo.com'
# Email of the single officer who performs every action.
OFFICER_EMAIL = 'inspector@demo.com'


def _application_number():
    import uuid
    while True:
        number = f'DEMO-{now().year}-{uuid.uuid4().hex[:6].upper()}'
        if not Application.query.filter_by(application_number=number).first():
            return number


def _times(base, d):
    return base - timedelta(days=d)


def _ensure_demo_business(demo_user, name, sector, city, business_type, fire_risk):
    biz = Business.query.filter_by(name=name).first()
    if biz:
        return biz
    biz = Business(
        id=gen_id(), owner_id=demo_user.id, name=name, owner_name=demo_user.name,
        business_type=business_type, sector=sector, state='Demonstration State',
        district='Demo District', city=city,
        address='Demonstration premises — not a real address',
        investment_amount=3500000, employee_count=18, size_category='SMALL',
        is_manufacturing=sector == 'MANUFACTURING', handles_food=sector == 'RESTAURANT',
        uses_hazardous=sector in ['MANUFACTURING', 'CHEMICAL'],
        uses_heavy_machinery=sector == 'MANUFACTURING', has_physical_infra=True,
        env_approval_applicable=sector == 'MANUFACTURING',
        fire_risk=fire_risk, status='ACTIVE',
    )
    db.session.add(biz)
    db.session.flush()
    return biz


def _ensure_documents(app, count=2, verified=True):
    """Give a demo application representative documents. Idempotent per app."""
    if Document.query.filter_by(application_id=app.id).first():
        return
    reqs = DocumentRequirement.query.filter_by(approval_type_id=app.approval_type_id).limit(count).all()
    if not reqs:
        reqs = [None] * count
    for i, req in enumerate(reqs):
        doc = Document(
            id=gen_id(), application_id=app.id, business_id=app.business_id,
            requirement_id=req.id if req else None, uploader_id=app.applicant_id,
            filename=f'demo_doc_{i}.pdf', original_filename=f'Document {i + 1}.pdf',
            doc_type=req.code if req else 'GENERAL', mime_type='application/pdf',
            file_size=240000 + i * 12000,
            status='VERIFIED' if verified else 'REJECTED',
            verification_status='VERIFIED' if verified else 'INCOMPLETE',
            verification_notes=('SIMULATED AI verification for the SIH demo — compiled, not a real government document.'
                                if verified else 'Missing / not yet submitted for this requirement.'),
            uploaded_at=_times(now(), 4), verified_at=_times(now(), 2),
        )
        db.session.add(doc)


def _assign_and_review(app, officer_id):
    """Attach the single officer assignment + completed AI review + audit trail."""
    app.assigned_officer_id = officer_id
    app.ai_reviewed_at = app.ai_reviewed_at or _times(now(), 1)
    if not ApplicationAssignment.query.filter_by(application_id=app.id).first():
        db.session.add(ApplicationAssignment(
            id=gen_id(), application_id=app.id, officer_id=officer_id,
            assigned_by_id=None, auto_routed=True, status='ACTIVE', assigned_at=_times(now(), 1),
        ))
    if not ApplicationStatusHistory.query.filter_by(application_id=app.id).first():
        db.session.add(ApplicationStatusHistory(
            application_id=app.id, status=app.status,
            changed_by_id=officer_id,
            notes='SIMULATED: seeded demo application for the Licence Officer / Inspector action demo.',
        ))
    if not AuditLog.query.filter_by(application_id=app.id, action='DEMO_SEEDED').first():
        db.session.add(AuditLog(
            application_id=app.id, user_id=officer_id, action='DEMO_SEEDED',
            details=f'Seeded demo application {app.application_number} at status {app.status} for demonstration.',
        ))


def _ensure_application(demo_user, biz, approval_code, status, officer_id,
                        correction_notes=None, ai_decision=None,
                        ai_decision_summary=None, notes=None):
    """Create (or return) one demo application for a business + licence."""
    at = ApprovalType.query.filter_by(code=approval_code).first()
    if not at:
        return None
    app = Application.query.filter_by(business_id=biz.id, approval_type_id=at.id).first()
    if not app:
        app = Application(
            id=gen_id(), application_number=_application_number(), business_id=biz.id,
            approval_type_id=at.id, department_id=at.department_id,
            applicant_id=demo_user.id, status=status,
            risk_level=at.requires_inspection and 'MEDIUM' or 'LOW',
            ai_decision=ai_decision, ai_decision_summary=ai_decision_summary,
            submission_date=_times(now(), 6), sla_deadline=now() + timedelta(days=max(1, at.sla_days or 10)),
            correction_notes=correction_notes, notes=notes,
        )
        db.session.add(app)
        db.session.flush()
    else:
        # Keep an existing seeded demo app aligned with the desired state so a
        # partial seed can be repaired, but never overwrite a decision already
        # made through the live officer workflow (APPROVED/REJECTED are terminal).
        if app.status not in ('APPROVED', 'REJECTED', 'EXPIRED'):
            app.status = status
            app.correction_notes = correction_notes
            app.ai_decision = ai_decision
            app.ai_decision_summary = ai_decision_summary
        db.session.flush()
    _assign_and_review(app, officer_id)
    if approval_code in ('FSSAI', 'FACTORY_LIC', 'PHPARMO_DEMO', 'PHARMACY_DEMO', 'HAZ_MAT'):
        _ensure_documents(app, count=2, verified=(status != 'CORRECTION_REQUIRED'))
    return app


def _ensure_inspection(app, status, result=None, scheduled_base_days=2):
    """Create OR reset the inspection(s) for an application to the target demo
    state. Idempotent and fully deterministic on every run so a restarted demo
    always shows the pristine lifecycle story (no stale, half-completed
    inspections left over from a previous session)."""
    ins = Inspection.query.filter_by(application_id=app.id).first()
    if not ins:
        ins = Inspection(
            id=gen_id(), application_id=app.id, inspector_id=app.assigned_officer_id,
            assigned_by_id=app.assigned_officer_id,
            status='PENDING',
            scheduled_date=now() + timedelta(days=scheduled_base_days),
        )
        db.session.add(ins)
        db.session.flush()
    # Always reset to the target demo state.
    if status == 'SCHEDULED':
        ins.status = 'SCHEDULED'
        ins.inspector_id = app.assigned_officer_id
        ins.scheduled_date = now() + timedelta(days=scheduled_base_days)
        ins.completed_date = None
        ins.overall_result = None
        ins.recommendation = None
        ins.report_submitted_at = None
        db.session.flush()
    elif status == 'COMPLETED':
        ins.status = 'COMPLETED'
        ins.inspector_id = app.assigned_officer_id
        ins.scheduled_date = _times(now(), 2)
        ins.overall_result = result or 'PASS'
        ins.recommendation = 'APPROVE' if (result or 'PASS') == 'PASS' else 'REJECT'
        ins.remarks = 'SIMULATED inspection completed. Premises found compliant for the SIH demo.'
        ins.report_submitted_at = _times(now(), 1)
        ins.completed_date = _times(now(), 1)
        db.session.flush()
    return ins


def _clear_inspections(app):
    """Remove any live inspections from a pre-decision demo application so the
    decision-pending/correction states stay clean (no orphaned inspection)."""
    for ins in Inspection.query.filter_by(application_id=app.id).all():
        if ins.status not in ('COMPLETED', 'CANCELLED'):
            db.session.delete(ins)
    db.session.flush()


def ensure_officer_demo_applications():
    """Create the 6 demo applications that power the officer action demo.

    Returns the list of demo work items (dicts) that surfaced/appeared, useful
    for logging. Idempotent — safe to call on every server start.
    """
    created = []

    demo_user = User.query.filter_by(email=DEMO_APPLICANT_EMAIL).first()
    officer = User.query.filter_by(email=OFFICER_EMAIL).first()
    if not demo_user or not officer or officer.role != 'OFFICER':
        return created

    # 1. GreenLeaf Foods — FSSAI Food Licence — READY FOR REVIEW
    spam = {
        'name': 'GreenLeaf Foods', 'sector': 'RESTAURANT', 'city': 'Mumbai',
        'business_type': 'RESTAURANT', 'fire_risk': 'MEDIUM',
        'licence': 'FSSAI', 'status': 'DECISION_PENDING',
        'notes': 'AI DEMO: simulated parallel departmental review — ready for officer review.',
    }
    # 2. Metro Tools & Engineering — Factory Licence — READY FOR REVIEW
    # 3. Sunrise Trading Co. — Trade Licence — CORRECTION REQUIRED
    # 4. Apex Manufacturing Unit — Factory Licence — INSPECTION SCHEDULED
    # 5. CarePlus Pharmacy (existing) — Pharmacy Compliance — INSPECTION COMPLETED / PASS
    # 6. QuickServe Chemicals — Hazardous Material — READY FOR REVIEW / AI FLAGGED

    defs = [
        # (business key, licence code, status, extras)
        ('greenleaf', 'FSSAI', 'DECISION_PENDING', {}),
        ('metro', 'FACTORY_LIC', 'DECISION_PENDING', {}),
        ('sunrise', 'TRADE_LIC', 'CORRECTION_REQUIRED',
         {'correction_notes': 'Updated address proof is required.',
          'ai_decision_summary': 'Documents flagged; an updated address proof is required to continue.'}),
        ('apex', 'FACTORY_LIC', 'INSPECTION_SCHEDULED', {}),
        ('careplus', 'PHARMACY_DEMO', 'INSPECTION_COMPLETED', {}),
        ('quickserve', 'HAZ_MAT', 'DECISION_PENDING',
         {'ai_decision': 'REJECT',
          'ai_decision_summary': 'AI flagged hazardous-material compliance gaps. Documents are incomplete.'}),
    ]

    businesses = {
        'greenleaf': _ensure_demo_business(demo_user, 'GreenLeaf Foods', 'RESTAURANT', 'Mumbai', 'RESTAURANT', 'MEDIUM'),
        'metro': _ensure_demo_business(demo_user, 'Metro Tools & Engineering', 'MANUFACTURING', 'Pune', 'MANUFACTURING_UNIT', 'HIGH'),
        'sunrise': _ensure_demo_business(demo_user, 'Sunrise Trading Co.', 'RETAIL', 'Delhi', 'RETAIL_BUSINESS', 'LOW'),
        'apex': _ensure_demo_business(demo_user, 'Apex Manufacturing Unit', 'MANUFACTURING', 'Surat', 'MANUFACTURING_UNIT', 'HIGH'),
        'quickserve': _ensure_demo_business(demo_user, 'QuickServe Chemicals', 'CHEMICAL', 'Vadodara', 'MANUFACTURING_UNIT', 'HIGH'),
        'careplus': Business.query.filter_by(name='CarePlus Pharmacy').first(),
    }

    for key, licence_code, status, extras in defs:
        biz = businesses[key]
        if not biz:
            continue
        app = _ensure_application(
            demo_user, biz, licence_code, status, officer.id,
            correction_notes=extras.get('correction_notes'),
            ai_decision=extras.get('ai_decision'),
            ai_decision_summary=extras.get('ai_decision_summary'),
            notes=extras.get('notes'),
        )
        if not app:
            continue
        # Inspection-conditioned demo states.
        if status == 'INSPECTION_SCHEDULED':
            _ensure_inspection(app, 'SCHEDULED', scheduled_base_days=2)
        elif status == 'INSPECTION_COMPLETED':
            _ensure_inspection(app, 'COMPLETED', result='PASS')
        else:
            # Decision-pending / correction states must not carry a live,
            # half-completed inspection from a previous session.
            _clear_inspections(app)
        created.append({
            'application_number': app.application_number,
            'business': biz.name,
            'licence': licence_code,
            'status': status,
        })

    db.session.commit()
    return created
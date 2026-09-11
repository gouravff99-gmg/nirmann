"""
NIRMAN AI Decision & Compliance Engine
======================================
Deterministic, rule-based compliance evaluation for the AI Compliance Agent.

HOW IT WORKS
------------
1. Risk assessment:  compute a 0-100 score from the business profile.
2. Checklist generation: gather every configured ApprovalType whose rules match
   the business (from the ApprovalRule table).
3. Decision evaluation: for each active application, combine
   - the matched checklist (are all mandatory approvals accounted for?)
   - document verification (VALID / CORRECTION / MISSING / EXPIRED)
   - inspection results (PASS / FAIL / conditional) when required
   - SLA health
   to produce APPROVE / CLARIFY / REJECT.

The local LLM is ONLY used to enrich the human-readable explanation; it never
decides. If it is offline we fall back to a plain deterministic explanation.

Every call that mutates state persists an AuditLog row so the agent remains
transparent and auditable (AI never blindly approves).
"""
import json
from datetime import datetime, timezone

from .. import db
from ..models import (
    Application, ApplicationStatusHistory, ApprovalRule, ApprovalType, AuditLog,
    Document, DocumentRequirement, Inspection, Notification, User, gen_id,
)
from . import ai_service
from .routing import assign_officer


def now():
    return datetime.now(timezone.utc)


def _actor():
    """The AI Compliance Agent system identity (created by seed/system)."""
    return User.query.filter_by(email='ai-agent@system.demo').first()


def evaluate_rules(business, approval_type_code=None):
    """
    Return all ApprovalTypes applicable to a business by evaluating the
    configured ApprovalRule rows against its profile. Returns a list of
    dicts describing each matched approval, its matched rules and why.
    """
    business_flags = {
        'sector': business.sector,
        'size_category': business.size_category,
        'employee_count': business.employee_count,
        'fire_risk': business.fire_risk,
    }
    # boolean flags
    for flag in ['is_manufacturing', 'handles_food', 'involves_construction',
                 'uses_hazardous', 'uses_heavy_machinery', 'has_physical_infra',
                 'env_approval_applicable']:
        business_flags[flag] = bool(getattr(business, flag, False))

    matched = {}
    ruleset = ApprovalRule.query.all()
    for rule in ruleset:
        value = business_flags.get(rule.condition_field)
        ok = _eval_rule(value, rule.condition_operator, rule.condition_value)
        entry = matched.setdefault(rule.approval_type_id, {
            'approval_type': rule.approval_type,
            'matched_rules': [],
            'any_mandatory': False,
        })
        if ok:
            entry['matched_rules'].append(rule)
            if rule.is_mandatory:
                entry['any_mandatory'] = True

    result = []
    for approval_id, entry in matched.items():
        at = entry['approval_type']
        if approval_type_code and at.code != approval_type_code:
            continue
        result.append({
            'approval_type': at,
            'matched_rules': entry['matched_rules'],
            'mandatory': entry['any_mandatory'],
            'why': [r.condition_field for r in entry['matched_rules']],
        })
    result.sort(key=lambda x: (x['approval_type'].priority, x['approval_type'].code))
    return result


def _eval_rule(value, operator, rule_value):
    if operator == 'always':
        return True
    if operator == 'true':
        return value is True
    if operator == 'eq':
        return str(value).upper() == str(rule_value).upper()
    if operator == 'in':
        if rule_value is None:
            return False
        options = [o.strip().upper() for o in rule_value.split(',')]
        return str(value).upper() in options
    if operator == 'gte':
        try:
            return int(value or 0) >= int(float(rule_value))
        except (TypeError, ValueError):
            return False
    if operator == 'lte':
        try:
            return int(value or 0) <= int(float(rule_value))
        except (TypeError, ValueError):
            return False
    return False


def compute_risk(business):
    """Compute a deterministic 0-100 risk score for a business profile."""
    score = 0
    factors = []
    def add(points, label, level):
        nonlocal score
        score += points
        factors.append({'factor': label, 'impact': f'+{points}', 'level': level})

    if business.is_manufacturing:
        add(25, 'Manufacturing operations', 'high')
    if business.uses_hazardous:
        add(22, 'Hazardous material usage', 'high')
    if business.handles_food:
        add(12, 'Food handling', 'medium')
    if business.env_approval_applicable:
        add(15, 'Environmental impact', 'medium')
    if business.fire_risk == 'HIGH':
        add(18, 'High fire-risk premises', 'high')
    elif business.fire_risk == 'MEDIUM':
        add(8, 'Medium fire-risk premises', 'medium')
    employees = business.employee_count or 0
    if employees > 50:
        add(10, f'Large workforce ({employees})', 'medium')
    elif employees > 10:
        add(5, f'Moderate workforce ({employees})', 'low')

    score = min(score, 100)
    if score < 30:
        level, workflow, rec = 'LOW', 'STREAMLINED', 'Eligible for streamlined automated processing.'
    elif score < 60:
        level, workflow, rec = 'MEDIUM', 'STANDARD', 'Standard verification with enhanced document scrutiny.'
    else:
        level, workflow, rec = 'HIGH', 'ENHANCED', 'Enhanced verification; inspection mandatory; accountable admin review required.'
    return {'score': score, 'level': level, 'workflow': workflow,
            'recommendation': rec, 'factors': factors}


# Document review states understood by the engine. APPROVED and REJECTED are the
# authoritative final per-document states that a licence officer assigns by
# reviewing each required document individually. VERIFIED is a legacy state kept
# for seeded/reused rows. RESUBMISSION_REQUIRED is a bad terminal-ish state that
# the applicant resolves by uploading a corrected document (new version).
_DOC_REVIEWED_OK = ('APPROVED', 'VERIFIED')  # VERIFIED kept for legacy seeded rows
_DOC_REVIEWED_BAD = ('REJECTED', 'RESUBMISSION_REQUIRED')
_DOC_STATUS_LABELS = {
    'VALIDATION_PENDING': 'validation pending',
    'UNDER_OFFICER_REVIEW': 'under officer review',
    'UNDER_REVIEW': 'under review',
    'RESUBMISSION_REQUIRED': 'resubmission required',
    'REJECTED': 'rejected',
    'UPLOADED': 'uploaded',
    'NOT_UPLOADED': 'not uploaded',
}


def _requirements_for(app):
    """Mandatory document requirements an application must satisfy to advance."""
    if app.approval_type:
        return [r for r in app.approval_type.document_requirements if r.is_mandatory]
    return DocumentRequirement.query.filter_by(
        approval_type_id=app.approval_type_id, is_mandatory=True).all()


def _document_state(doc):
    """Normalised per-document review state (never mutates other documents)."""
    return (doc.verification_status or 'UPLOADED').upper()


def all_mandatory_documents_approved(app):
    """True only when EVERY required document for this application has
    been individually reviewed and approved (APPROVED or VERIFIED).
    UPLOADED documents count as unreviewed; the requirement must have
    all its documents individually satisfied."""
    from ..models import Document as DocModel
    for req in _requirements_for(app):
        docs_for_req = DocModel.query.filter_by(application_id=app.id, requirement_id=req.id).all()
        if not docs_for_req:
            return False
        if not all(_document_state(d) in _DOC_REVIEWED_OK for d in docs_for_req):
            return False
    return True


def document_health(app):
    """Classify the submitted documents for an application.

    Status is derived from the full set of MANDATORY required documents (per
    the approval type), not merely the count of files uploaded so far. A single
    uploaded document therefore never produces a 'VERIFIED' health for an
    application that still needs additional documents.
    """
    requirements = _requirements_for(app)
    from ..models import Document as DocModel
    if not requirements:
        return {'status': 'PENDING', 'verified': 0, 'total': 0, 'issues': []}
    verified = 0
    issues = []
    for req in requirements:
        docs_for_req = DocModel.query.filter_by(application_id=app.id, requirement_id=req.id).all()
        if not docs_for_req:
            issues.append(f'{req.name}: not uploaded')
            continue
        req_verified = True
        for d in docs_for_req:
            s = _document_state(d)
            if s in _DOC_REVIEWED_BAD:
                issues.append(f'{req.name}: {_DOC_STATUS_LABELS.get(s, s.lower())}')
                req_verified = False
                break
            if s not in _DOC_REVIEWED_OK:
                issues.append(f'{req.name}: {_DOC_STATUS_LABELS.get(s, s.lower())}')
                req_verified = False
                break
        if req_verified:
            verified += 1
    total = len(requirements)
    if issues:
        status = 'CORRECTION'
    elif verified == total:
        status = 'VERIFIED'
    else:
        status = 'PENDING'
    return {'status': status, 'verified': verified, 'total': total, 'issues': issues}


def pick_inspector():
    """Choose the LICENCE OFFICER with the fewest open tasks (workload-balanced).

    Prevents the physical-inspection step from stacking on one officer and
    makes the Inspection view a real per-role view across users. The officer
    and inspector roles are combined, so this selects from OFFICER users.
    """
    inspectors = User.query.filter_by(role='OFFICER', is_active=True).all()
    if not inspectors:
        return None
    return min(
        inspectors,
        key=lambda u: Inspection.query.filter(
            Inspection.inspector_id == u.id,
            Inspection.status.in_(['ASSIGNED', 'SCHEDULED', 'STARTED']),
        ).count(),
    )


def _review_notice(app, actor_id, title, message, notif_type='INFO'):
    db.session.add(Notification(
        user_id=app.applicant_id, title=title, message=message,
        type=notif_type, related_application_id=app.id,
    ))


def review_and_advance(app, actor=None, enrich=True):
    """Assess + persist an application review, then advance the coordinated
    workflow in one audited pass.

    The routing uses the engine's *checks* (documents verified and not
    rejected) rather than the final recommendation: an inspection-required
    application is intentionally held at CLARIFY until the physical inspection
    reports, so the recommendation alone could never route it forward.

    - inspection-required approvals with verified documents -> INSPECTION_REQUIRED
      (an ASSIGNED Inspection is created and handed to the least-loaded inspector)
    - everything else with verified documents -> DECISION_PENDING (Admin gate)
    - documents still pending/corrected -> stays in review, applicant notified
    """
    actor = actor or _actor()
    assessment = assess_application(app, enrich=enrich)
    persist_assessment(app, assessment, actor=actor)

    checks = assessment.get('checks', {})
    # A single application's own documents are the routing signal; the full
    # business checklist stays visible in the AI panel and is not a blocker
    # for this approval's inspection/decision stage. Crucially the gate is
    # "every required document individually approved" — one uploaded/approved
    # document can never approve the rest of the set.
    docs_ok = all_mandatory_documents_approved(app)
    # NOTE: `checks` retains the human-readable document_health for the AI
    # summary, while the strict per-requirement gate drives the workflow.
    advance = docs_ok and assessment.get('decision') != 'REJECT'
    approval_type = app.approval_type

    if app.status in ['SUBMITTED', 'UNDER_REVIEW', 'DOCUMENT_VALIDATION',
                      'CORRECTION_REQUIRED', 'ADDITIONAL_DOCUMENTS_REQUIRED']:
        if advance:
            # Bring a corrected / resubmitted application back into the normal
            # review lane before routing it forward.
            if app.status in ('CORRECTION_REQUIRED', 'ADDITIONAL_DOCUMENTS_REQUIRED'):
                app.status = 'DOCUMENT_VALIDATION'
                db.session.add(ApplicationStatusHistory(
                    application_id=app.id, status='DOCUMENT_VALIDATION',
                    changed_by_id=actor.id if actor else None,
                    notes='AI revalidation passed after documents were restored to the approved state.',
                ))
            if approval_type and approval_type.requires_inspection:
                if not Inspection.query.filter_by(application_id=app.id).first():
                    inspector = pick_inspector()
                    db.session.add(Inspection(
                        id=gen_id(), application_id=app.id,
                        inspector_id=inspector.id if inspector else None,
                        assigned_by_id=actor.id if actor else None, status='ASSIGNED',
                    ))
                    if inspector:
                        db.session.add(Notification(
                            user_id=inspector.id, title='Inspection assigned',
                            message=f'Application {app.application_number} passed AI verification and now needs a physical inspection.',
                            type='INFO', related_application_id=app.id,
                        ))
                app.status = 'INSPECTION_REQUIRED'
                db.session.add(ApplicationStatusHistory(
                    application_id=app.id, status='INSPECTION_REQUIRED',
                    changed_by_id=actor.id if actor else None,
                    notes='AI verification passed; a physical inspection is now required.',
                ))
                db.session.add(AuditLog(
                    application_id=app.id, user_id=actor.id if actor else None,
                    action='AI_REVIEW_COMPLETED',
                    details=f'AI decision {assessment["decision"]} ({assessment["confidence"]}%): documents verified; inspection routed to a qualified inspector.',
                ))
                _review_notice(app, actor.id if actor else None, 'Inspection required',
                               'AI verification passed. A physical inspection is now required before the final decision.')
                # Keep the accountable licensing officer on the record from the
                # outset so their inbox/dashboard reflects the pending pipeline.
                assign_officer(app, actor=actor, auto_routed=True)
            else:
                app.status = 'DECISION_PENDING'
                db.session.add(ApplicationStatusHistory(
                    application_id=app.id, status='DECISION_PENDING',
                    changed_by_id=actor.id if actor else None,
                    notes='AI verification passed; routed to the accountable licensing officer decision.',
                ))
                db.session.add(AuditLog(
                    application_id=app.id, user_id=actor.id if actor else None,
                    action='AI_REVIEW_COMPLETED',
                    details=f'AI decision {assessment["decision"]} ({assessment["confidence"]}%): documents verified; queued for Officer decision.',
                ))
                _review_notice(app, actor.id if actor else None, 'Ready for officer decision',
                               'AI verification passed. Your application is queued for the accountable licensing officer decision.')
                # Auto-route to the licensing officer authorised for this licence.
                officer = assign_officer(app, actor=actor, auto_routed=True)
                if officer:
                    db.session.add(Notification(
                        user_id=officer.user_id, title='Application ready for decision',
                        message=f'Application {app.application_number} ({app.approval_type.code}) passed verification and is now assigned to you for decision.',
                        type='INFO', related_application_id=app.id,
                    ))
        else:
            if app.status == 'SUBMITTED':
                app.status = 'UNDER_REVIEW'
                db.session.add(ApplicationStatusHistory(
                    application_id=app.id, status='UNDER_REVIEW',
                    changed_by_id=actor.id if actor else None,
                    notes='AI Compliance Agent began automated review.',
                ))
            _review_notice(app, actor.id if actor else None, 'AI review action needed',
                           f'AI compliance check: {assessment["decision"]}. Add the missing documents and re-submit for another review.')
    return assessment


def inspection_health(app):
    """Interpret the most recent inspection result for an application."""
    inspection = Inspection.query.filter_by(application_id=app.id)\
        .order_by(Inspection.created_at.desc()).first()
    if not inspection:
        return {'required': bool(app.approval_type and app.approval_type.requires_inspection),
                'status': 'NONE', 'result': None}
    return {'required': True, 'status': inspection.status,
            'result': inspection.overall_result}


def assess_application(app, enrich=True):
    """
    Produce a structured AI decision for a single application. Returns a dict
    summarising every step and the final recommendation. Does NOT mutate state.
    """
    business = app.business
    risk = compute_risk(business)

    # Evaluate the checklist for completeness.
    applicable = evaluate_rules(business)
    codes_present = {a.approval_type.code for a in app.business.applications if a.approval_type}
    mandatory = [e for e in applicable if e['mandatory']]
    checklist = []
    for e in applicable:
        at = e['approval_type']
        has_app = at.code in codes_present
        checklist.append({
            'code': at.code, 'name': at.name, 'department': at.department.name if at.department else None,
            'mandatory': e['mandatory'], 'has_application': has_app,
            'why': ', '.join(at.document_requirements and e['why'] or e['why']) or at.code,
        })

    dh = document_health(app)
    ih = inspection_health(app)

    checks = {
        'risk': {'level': risk['level'], 'score': risk['score']},
        'documents': dh,
        'inspection': ih,
        'checklist_complete': all(c['has_application'] for c in checklist if c['mandatory']),
    }

    decision = None
    # Rule-based decision logic (the LLM never decides).
    if not checks['checklist_complete']:
        decision = 'CLARIFY'
        reason = 'One or more mandatory configured approvals is not present for this business profile.'
    elif dh['status'] == 'CORRECTION':
        decision = 'CLARIFY'
        reason = 'Submitted documents require correction or contain expired/rejected items.'
    elif dh['status'] == 'MISSING':
        decision = 'CLARIFY'
        reason = 'Required documents are missing.'
    elif ih['required'] and ih['result'] is None:
        decision = 'CLARIFY'
        reason = 'A physical inspection is required or has not reported a result yet.'
    elif ih['required'] and ih['result'] == 'FAIL':
        decision = 'REJECT'
        reason = 'The mandatory physical inspection returned a FAIL result.'
    elif risk['level'] == 'HIGH':
        decision = 'CLARIFY'
        reason = 'High-risk profile requires an accountable human (Admin) review before approval.'
    elif dh['status'] == 'VERIFIED':
        decision = 'APPROVE'
        reason = 'All mandatory approvals present, documents verified and no outstanding inspection.'
    else:
        decision = 'CLARIFY'
        reason = 'Document verification is still pending.'

    recommendation = decision
    confidence = _confidence(decision, checks)

    # Build the raw explanation.
    raw = (f'{reason} Risk: {risk["level"]} ({risk["score"]}/100). '
           f'Documents: {dh["status"]} ({dh["verified"]}/{dh["total"]}). '
           f'Inspection: {ih["status"]}.')

    explanation = raw
    used_llm = False
    if enrich:
        try:
            enriched, used_llm = ai_service.enrich_explanation(raw)
            if used_llm and enriched:
                explanation = enriched
        except Exception:
            used_llm = False

    return {
        'application_id': app.id,
        'application_number': app.application_number,
        'business': business.name,
        'decision': decision,
        'recommendation': recommendation,
        'risk': risk,
        'checks': checks,
        'checklist': checklist,
        'confidence': confidence,
        'reason': reason,
        'explanation': explanation,
        'used_llm': used_llm,
        'evaluated_at': now().isoformat(),
    }


def _confidence(decision, checks):
    base = {'APPROVE': 88, 'REJECT': 92, 'CLARIFY': 74}[decision]
    if checks['documents']['status'] == 'VERIFIED':
        base += 6
    if checks['inspection'].get('result') == 'PASS':
        base += 6
    if checks['risk']['level'] == 'LOW':
        base += 3
    return min(99, base)


def persist_assessment(app, assessment, actor=None):
    """Write the assessment onto the Application row and append an audit entry."""
    actor = actor or _actor()
    app.risk_score = assessment['risk']['score']
    app.risk_level = assessment['risk']['level']
    app.ai_decision = assessment['decision']
    app.ai_decision_confidence = assessment['confidence']
    app.ai_decision_summary = assessment['explanation']
    app.ai_decision_rules = json.dumps([c['code'] for c in assessment['checklist']])
    app.ai_reviewed_at = now()
    db.session.add(AuditLog(
        application_id=app.id,
        user_id=actor.id if actor else None,
        action=f'AI_DECISION_{assessment["decision"]}',
        details=assessment['explanation'],
    ))
    db.session.commit()
    return app


def review_application(app_id, actor=None, commit=True):
    """Assess + persist a single application's AI review."""
    app = Application.query.get_or_404(app_id)
    assessment = assess_application(app)
    app.risk_score = assessment['risk']['score']
    app.risk_level = assessment['risk']['level']
    app.ai_decision = assessment['decision']
    app.ai_decision_confidence = assessment['confidence']
    app.ai_decision_summary = assessment['explanation']
    app.ai_decision_rules = json.dumps([c['code'] for c in assessment['checklist']])
    app.ai_reviewed_at = now()
    actor = actor or _actor()
    db.session.add(AuditLog(
        application_id=app.id,
        user_id=actor.id if actor else None,
        action=f'AI_DECISION_{assessment["decision"]}',
        details=assessment['explanation'],
    ))
    if commit:
        db.session.commit()
    return assessment

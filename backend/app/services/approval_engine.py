"""
NIRMAN Dynamic Approval Engine
================================
This is the core rule-based approval engine.
Rules are evaluated against a Business's attributes to generate a
customized approval checklist.

This module is intentionally SEPARATE from UI components so that
real government rules/APIs can replace this in production.
"""
from ..models import ApprovalType, ApprovalRule, BusinessLicenceAssignment, AuditLog
from .. import db


def assign_licences_for_business(business):
    """Persist the sector→licence mapping for a business in SQLite.

    Runs the rule engine once, then reconciles the `business_licence_assignments`
    table to exactly match the derived checklist. The licence assignment is thus
    a server-side, persisted record — the frontend only renders it, and
    create_application enforces it.
    """
    checklist = generate_approval_checklist(business)
    desired = {item['approval_type']['id']: {
        'is_mandatory': item.get('is_mandatory', True),
        'why_triggered': item.get('why_triggered') or item['approval_type'].get('why_required') or 'Required for your business profile',
    } for item in checklist}

    existing = {a.approval_type_id: a
                for a in BusinessLicenceAssignment.query.filter_by(business_id=business.id).all()}

    # Remove assignments that no longer match the business profile.
    for type_id in list(existing.keys()):
        if type_id not in desired:
            db.session.delete(existing[type_id])
            db.session.add(AuditLog(application_id=None, user_id=None, action='LICENCE_UNASSIGNED',
                                    details=f'Licence {existing[type_id].approval_type_id} no longer required for this business profile.'))
            del existing[type_id]

    # Insert or refresh current assignments.
    for type_id, info in desired.items():
        if type_id in existing:
            existing[type_id].is_mandatory = info['is_mandatory']
            existing[type_id].why_triggered = info['why_triggered']
        else:
            db.session.add(BusinessLicenceAssignment(
                business_id=business.id, approval_type_id=type_id,
                is_mandatory=info['is_mandatory'], why_triggered=info['why_triggered'],
            ))

    db.session.flush()
    rows = BusinessLicenceAssignment.query.filter_by(business_id=business.id).all()
    return [r.to_dict() for r in rows]


def evaluate_rule(rule, business):
    """Evaluate a single approval rule against a business."""
    field = rule.condition_field
    operator = rule.condition_operator
    value = rule.condition_value

    # Get the business attribute
    business_value = getattr(business, field, None)

    if operator == 'true':
        return business_value is True or str(business_value).lower() == 'true'
    
    elif operator == 'false':
        return business_value is False or str(business_value).lower() == 'false'
    
    elif operator == 'eq':
        return str(business_value).upper() == str(value).upper()
    
    elif operator == 'ne':
        return str(business_value).upper() != str(value).upper()
    
    elif operator == 'in':
        values = [v.strip().upper() for v in value.split(',')]
        return str(business_value).upper() in values
    
    elif operator == 'gte':
        try:
            return float(business_value or 0) >= float(value)
        except (ValueError, TypeError):
            return False
    
    elif operator == 'lte':
        try:
            return float(business_value or 0) <= float(value)
        except (ValueError, TypeError):
            return False
    
    elif operator == 'gt':
        try:
            return float(business_value or 0) > float(value)
        except (ValueError, TypeError):
            return False
    
    elif operator == 'lt':
        try:
            return float(business_value or 0) < float(value)
        except (ValueError, TypeError):
            return False
    
    elif operator == 'always':
        return True
    
    return False


def generate_approval_checklist(business):
    """
    Generate a customized approval checklist for a given business.
    
    The engine works by:
    1. Getting all approval types with their associated rules
    2. For each approval type, evaluating ALL its rules against the business
    3. An approval type is included if ANY of its rules match
    4. Returns sorted list of applicable approval types with metadata
    
    Future: Replace this with government rule engine API calls.
    """
    all_approval_types = ApprovalType.query.all()
    all_rules = ApprovalRule.query.all()
    
    # Group rules by approval_type_id
    rules_by_type = {}
    for rule in all_rules:
        if rule.approval_type_id not in rules_by_type:
            rules_by_type[rule.approval_type_id] = []
        rules_by_type[rule.approval_type_id].append(rule)
    
    checklist = []
    
    for approval_type in all_approval_types:
        rules = rules_by_type.get(approval_type.id, [])
        
        # If no rules defined, always include (universal approval)
        if not rules:
            applicable = True
        else:
            # Check if any rule matches (OR logic between different rule groups)
            # Within same field, OR logic; overall OR between rule groups
            applicable = any(evaluate_rule(r, business) for r in rules)
        
        if applicable:
            checklist.append({
                'approval_type': approval_type.to_dict(),
                'is_mandatory': any(r.is_mandatory for r in rules) if rules else True,
                'why_triggered': get_trigger_reason(rules, business),
                'priority': approval_type.priority
            })
    
    # Sort by priority (lower = higher priority)
    checklist.sort(key=lambda x: x['priority'])
    
    return checklist


def get_trigger_reason(rules, business):
    """Generate a human-readable explanation of why this approval is required."""
    reasons = []
    for rule in rules:
        if evaluate_rule(rule, business):
            field = rule.condition_field
            readable = {
                'handles_food': 'Your business handles food products',
                'is_manufacturing': 'Your business involves manufacturing',
                'involves_construction': 'Your business involves construction',
                'uses_hazardous': 'Your business uses hazardous materials',
                'env_approval_applicable': 'Your business may have environmental impact',
                'fire_risk': f'Your business has {getattr(business, field, "")} fire risk',
                'sector': f'Required for {getattr(business, field, "")} sector businesses',
                'employee_count': f'Required for businesses with {getattr(business, field, 0)} or more employees',
                'has_physical_infra': 'Your business has physical infrastructure',
                'uses_heavy_machinery': 'Your business uses heavy machinery',
            }.get(field, f'Required based on your business profile')
            reasons.append(readable)
    
    return '; '.join(reasons) if reasons else 'Required for your business type'

"""One-off idempotent script: add GST Registration and Shops & Establishment
approval types (+ docs) to an existing DB without a destructive reseed."""

from app import create_app, db
from app.models import ApprovalType, ApprovalRule, Department, DocumentRequirement, gen_id

app = create_app()

with app.app_context():
    changed = False

    gst_dept = Department.query.filter_by(code='GST').first()
    if not gst_dept:
        gst_dept = Department(
            id=gen_id(), name='Commercial Taxes Department', code='GST',
            description='Registers and governs GST compliance for businesses',
            avg_processing_days=3, sla_days=5,
        )
        db.session.add(gst_dept)
        db.session.flush()
        changed = True

    if not ApprovalType.query.filter_by(code='GST_REG').first():
        gst = ApprovalType(
            id=gen_id(), name='GST Registration', code='GST_REG', department_id=gst_dept.id,
            description='DEMO: GST Registration - Mandatory for businesses crossing the GST registration threshold — operates as the central tax registration for the business.',
            why_required='Mandatory for businesses crossing the GST registration threshold — operates as the central tax registration for the business.',
            requires_inspection=False, estimated_days=7, sla_days=15,
            validity_months=0, workflow_type='A', priority=0,
        )
        db.session.add(gst)
        db.session.flush()
        db.session.add(ApprovalRule(
            id=gen_id(), approval_type_id=gst.id,
            condition_field='has_physical_infra', condition_operator='always',
            condition_value=None, is_mandatory=True,
        ))
        for name, code, desc, is_mandatory in [
            ('PAN Card', 'PAN', 'Business PAN card', True),
            ('Aadhaar Card', 'IDENTITY', 'Proprietor Aadhaar card', True),
            ('Business Address Proof', 'BIZ_ADDRESS', 'Rental agreement or property documents', True),
            ('Bank Account Proof', 'BANK_PROOF', 'Cancelled cheque or bank statement for GST bank verification', True),
        ]:
            db.session.add(DocumentRequirement(
                id=gen_id(), approval_type_id=gst.id,
                name=name, code=code, description=desc, is_mandatory=is_mandatory,
            ))
        changed = True

    labour = Department.query.filter_by(code='LABOUR').first() or gst_dept
    if not ApprovalType.query.filter_by(code='SHOPS_EST').first():
        shops = ApprovalType(
            id=gen_id(), name='Shops & Establishment Registration', code='SHOPS_EST', department_id=labour.id,
            description='DEMO: Shops & Establishment Registration - Required for all shops and commercial establishments under the Shops and Establishments Act.',
            why_required='Required for all shops and commercial establishments under the Shops and Establishments Act.',
            requires_inspection=False, estimated_days=7, sla_days=10,
            validity_months=12, workflow_type='A', priority=1,
        )
        db.session.add(shops)
        db.session.flush()
        db.session.add(ApprovalRule(
            id=gen_id(), approval_type_id=shops.id,
            condition_field='has_physical_infra', condition_operator='always',
            condition_value=None, is_mandatory=True,
        ))
        for name, code, desc, is_mandatory in [
            ('Business Registration', 'BUSINESS_REGISTRATION', 'Registration certificate or partnership deed', True),
            ('Identity Proof', 'IDENTITY', 'Owner identity proof', True),
            ('Address Proof', 'ADDRESS_PROOF', 'Premises address proof', True),
        ]:
            db.session.add(DocumentRequirement(
                id=gen_id(), approval_type_id=shops.id,
                name=name, code=code, description=desc, is_mandatory=is_mandatory,
            ))
        changed = True

    if changed:
        db.session.commit()
        print('Added GST_REG / SHOPS_EST approval types + docs.')
    else:
        print('GST_REG / SHOPS_EST already present (or partly); no changes needed.')
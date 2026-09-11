"""
NIRMAN Database Seed Script
===========================
Creates all demo data for SIH presentation.
⚠️ ALL DATA IS DEMONSTRATION/PROTOTYPE DATA ONLY.
"""
from app import create_app, db
from app.models import (
    User, Department, ApprovalType, ApprovalRule, DocumentRequirement, Sector,
    Business, Application, ApplicationStatusHistory, Document,
    BusinessLicenceAssignment,
    Inspection, Certificate, Renewal, Notification, Grievance, AuditLog, Scheme
)
from app.routes.ai_agent import _ensure_demo_workflows
from app.services.approval_engine import assign_licences_for_business
import bcrypt
import uuid
from datetime import datetime, timezone, timedelta
import json
import random

def now():
    return datetime.now(timezone.utc)

def gen_id():
    return str(uuid.uuid4())

def gen_cert_number():
    return f"CERT-NIR-2026-{uuid.uuid4().hex[:8].upper()}"

def gen_ver_id():
    return f"VID-{uuid.uuid4().hex[:12].upper()}"

def hash_password(pwd):
    return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()

def seed():
    print("🌱 Seeding NIRMAN demo database...")

    # ===================== DEPARTMENTS =====================
    print("  Creating departments...")
    depts = {}
    dept_data = [
        ('Food Safety Department', 'FOOD_SAFETY', 'Regulates food safety standards and licensing', 12, 15),
        ('Fire Department', 'FIRE_DEPT', 'Issues Fire Safety NOC and conducts fire safety inspections', 10, 12),
        ('Pollution Control Board', 'POLLUTION', 'Issues pollution control consent and monitors emissions', 18, 21),
        ('Labour Department', 'LABOUR', 'Manages labour law compliance and registrations', 14, 20),
        ('Factory / Industrial Safety', 'FACTORY', 'Issues factory licences and oversees industrial safety', 20, 25),
        ('Local Municipal Authority', 'MUNICIPAL', 'Issues trade licences and local business permits', 7, 10),
        ('Building / Planning Authority', 'PLANNING', 'Approves building plans and construction projects', 30, 35),
        ('Electrical Safety Department', 'ELECTRICAL', 'Issues electrical safety certificates', 8, 10),
        ('Commercial Taxes Department', 'GST', 'Registers and governs GST compliance for businesses', 3, 5),
    ]

    for name, code, desc, avg_days, sla in dept_data:
        d = Department(id=gen_id(), name=name, code=code, description=desc,
                       avg_processing_days=avg_days, sla_days=sla)
        db.session.add(d)
        depts[code] = d
    db.session.flush()

    # ===================== SECTORS =====================
    print("  Creating sector reference data...")
    sector_codes = [
        'FOOD_PROCESSING', 'FOOD_SERVICE', 'RESTAURANT', 'MANUFACTURING',
        'ELECTRONICS', 'CONSTRUCTION', 'REAL_ESTATE', 'RETAIL', 'WHOLESALE',
        'SERVICE', 'HEALTHCARE', 'EDUCATION', 'OTHER',
    ]
    for code in sector_codes:
        if not Sector.query.filter_by(code=code).first():
            db.session.add(Sector(code=code, label=code.replace('_', ' ').title()))
    db.session.flush()

    # ===================== APPROVAL TYPES =====================
    print("  Creating approval types...")
    ats = {}
    approval_data = [
        # (name, code, dept_code, why, requires_insp, days, sla, validity_months, workflow, priority)
        ('Business Registration', 'BIZ_REG', 'MUNICIPAL',
         'Every business must be registered with local authorities before commencing operations.',
         False, 7, 10, 60, 'A', 0),
        ('Trade Licence', 'TRADE_LIC', 'MUNICIPAL',
         'Required for all businesses operating commercially within municipal limits.',
         False, 7, 10, 12, 'A', 1),
        ('FSSAI Food Licence', 'FSSAI', 'FOOD_SAFETY',
         'Mandatory for all businesses involved in food manufacturing, processing, packaging, or sale.',
         True, 30, 45, 12, 'B', 2),
        ('Fire Safety NOC', 'FIRE_NOC', 'FIRE_DEPT',
         'Required for businesses with physical premises, especially those with fire risk or public access.',
         True, 10, 12, 12, 'B', 3),
        ('Pollution Control Consent (Consent to Operate)', 'POLLUTION_CTO', 'POLLUTION',
         'Required for industries that generate air, water, or solid waste pollution.',
         True, 21, 25, 12, 'B', 4),
        ('Factory Licence', 'FACTORY_LIC', 'FACTORY',
         'Required for manufacturing units with 10+ workers (or 20+ without power) under the Factories Act.',
         True, 30, 35, 12, 'B', 5),
        ('Labour Registration', 'LABOUR_REG', 'LABOUR',
         'Required for employers with 10+ employees for compliance with labour laws.',
         False, 14, 20, 12, 'A', 6),
        ('Electrical Safety Certificate', 'ELEC_SAFETY', 'ELECTRICAL',
         'Required for premises with high electrical load or industrial electrical installations.',
         True, 8, 10, 12, 'B', 7),
        ('Building Plan Approval', 'BUILD_PLAN', 'PLANNING',
         'Required before starting any construction or major renovation of physical premises.',
         True, 45, 60, 60, 'B', 8),
        ('Health NOC', 'HEALTH_NOC', 'FOOD_SAFETY',
         'Required for businesses serving food directly to consumers (restaurants, canteens, etc.).',
         False, 10, 14, 12, 'C', 9),
        ('Hazardous Material Licence', 'HAZ_MAT', 'POLLUTION',
         'Required for storage, handling, or transportation of hazardous chemicals or materials.',
         True, 21, 30, 12, 'B', 10),
        ('MSME Registration (Udyam)', 'UDYAM', 'MUNICIPAL',
         'Recommended for small and medium enterprises to access government schemes and benefits.',
         False, 1, 3, 0, 'A', 11),
        ('Pharmacy / Medical Retail Compliance (DEMO)', 'PHARMACY_DEMO', 'FOOD_SAFETY',
         'SIMULATED specialised pharmacy compliance workflow for SIH demonstration.',
         True, 14, 18, 12, 'B', 2),
        ('GST Registration', 'GST_REG', 'GST',
         'Mandatory for businesses crossing the GST registration threshold — operates as the central tax registration for the business.',
         False, 7, 15, 0, 'A', 0),
        ('Shops & Establishment Registration', 'SHOPS_EST', 'LABOUR',
         'Required for all shops and commercial establishments under the Shops and Establishments Act.',
         False, 7, 10, 12, 'A', 1),
    ]

    for name, code, dept_code, why, req_insp, days, sla, validity, workflow, priority in approval_data:
        at = ApprovalType(
            id=gen_id(), name=name, code=code,
            department_id=depts[dept_code].id,
            description=f'DEMO: {name} - {why}',
            why_required=why,
            requires_inspection=req_insp,
            estimated_days=days, sla_days=sla,
            validity_months=validity, workflow_type=workflow,
            priority=priority
        )
        db.session.add(at)
        ats[code] = at
    db.session.flush()

    # Set official government sources for the 6 Licence & Knowledge Center items
    OFFICIAL_SOURCES = {
        'FSSAI': [{'name': 'FSSAI Food License', 'url': 'https://foscos.fssai.gov.in/'}],
        'FIRE_NOC': [{'name': 'Fire Safety NOC', 'url': 'https://services.india.gov.in/'}],
        'GST_REG': [{'name': 'GST Registration', 'url': 'https://services.india.gov.in/service/detail/gst-registration-1'}],
        'LABOUR_REG': [{'name': 'Labour Registration', 'url': 'https://registration.shramsuvidha.gov.in/'}],
        'POLLUTION_CTO': [{'name': 'Pollution Control Consent', 'url': 'https://ocmms.nic.in/OCMMS_NEW/'}],
        'ELEC_SAFETY': [{'name': 'Electrical Safety Certificate', 'url': 'https://cea.nic.in/chief-electrical-inspectorate-division/?lang=en'}],
    }
    for code, sources in OFFICIAL_SOURCES.items():
        at = ats.get(code)
        if at:
            at.official_sources = json.dumps(sources)

    # ===================== APPROVAL RULES =====================
    print("  Creating approval rules...")
    rule_data = [
        # (approval_code, field, operator, value, is_mandatory)
        # Business Registration - always
        ('BIZ_REG', 'has_physical_infra', 'always', None, True),
        # Trade Licence - always
        ('TRADE_LIC', 'has_physical_infra', 'always', None, True),
        # FSSAI - food related
        ('FSSAI', 'handles_food', 'true', None, True),
        ('FSSAI', 'sector', 'in', 'FOOD_PROCESSING,FOOD_SERVICE,RESTAURANT,RETAIL', True),
        # Fire NOC - physical infra + fire risk
        ('FIRE_NOC', 'has_physical_infra', 'true', None, True),
        ('FIRE_NOC', 'fire_risk', 'in', 'MEDIUM,HIGH', True),
        ('FIRE_NOC', 'is_manufacturing', 'true', None, True),
        # Pollution Control
        ('POLLUTION_CTO', 'env_approval_applicable', 'true', None, True),
        ('POLLUTION_CTO', 'is_manufacturing', 'true', None, True),
        ('POLLUTION_CTO', 'uses_hazardous', 'true', None, True),
        # Factory Licence
        ('FACTORY_LIC', 'is_manufacturing', 'true', None, True),
        ('FACTORY_LIC', 'sector', 'in', 'MANUFACTURING,FOOD_PROCESSING', True),
        # Labour Registration
        ('LABOUR_REG', 'employee_count', 'gte', '10', True),
        # Electrical Safety
        ('ELEC_SAFETY', 'is_manufacturing', 'true', None, True),
        ('ELEC_SAFETY', 'uses_heavy_machinery', 'true', None, True),
        ('ELEC_SAFETY', 'sector', 'in', 'MANUFACTURING,ELECTRONICS', True),
        # Building Plan
        ('BUILD_PLAN', 'involves_construction', 'true', None, True),
        ('BUILD_PLAN', 'sector', 'in', 'CONSTRUCTION,REAL_ESTATE', True),
        # Health NOC
        ('HEALTH_NOC', 'handles_food', 'true', None, True),
        ('HEALTH_NOC', 'sector', 'in', 'RESTAURANT,FOOD_SERVICE', True),
        # Hazardous Material
        ('HAZ_MAT', 'uses_hazardous', 'true', None, True),
        # UDYAM - always for small/medium
        ('UDYAM', 'size_category', 'in', 'SMALL,MEDIUM', False),
        # GST Registration - always
        ('GST_REG', 'has_physical_infra', 'always', None, True),
        # Shops & Establishment - always
        ('SHOPS_EST', 'has_physical_infra', 'always', None, True),
        # Pharmacy demo
        ('PHARMACY_DEMO', 'sector', 'eq', 'HEALTHCARE', True),
    ]

    for approval_code, field, operator, value, is_mandatory in rule_data:
        if approval_code in ats:
            rule = ApprovalRule(
                id=gen_id(),
                approval_type_id=ats[approval_code].id,
                condition_field=field,
                condition_operator=operator,
                condition_value=value,
                is_mandatory=is_mandatory
            )
            db.session.add(rule)
    db.session.flush()

    # ===================== DOCUMENT REQUIREMENTS =====================
    print("  Creating document requirements...")
    doc_req_data = {
        'BIZ_REG': [
            ('PAN Card', 'PAN', 'Proprietor/Director PAN card', True),
            ('Identity Proof', 'IDENTITY', 'Aadhaar/Passport/Voter ID', True),
            ('Address Proof', 'ADDRESS_PROOF', 'Utility bill or bank statement', True),
            ('Business Address Proof', 'BIZ_ADDRESS', 'Rental agreement or property documents', True),
        ],
        'TRADE_LIC': [
            ('PAN Card', 'PAN', 'Business PAN card', True),
            ('Identity Proof', 'IDENTITY', 'Owner identity proof', True),
            ('Business Registration', 'BUSINESS_REGISTRATION', 'Certificate of incorporation or partnership deed', True),
            ('Address Proof', 'ADDRESS_PROOF', 'Business address proof', True),
        ],
        'FSSAI': [
            ('PAN Card', 'PAN', 'Business PAN card', True),
            ('Business Registration', 'BUSINESS_REGISTRATION', 'Certificate of incorporation', True),
            ('Property Documents', 'PROPERTY_DOCS', 'Property ownership or lease agreement', True),
            ('Layout Plan', 'LAYOUT_PLAN', 'Detailed layout plan of the food processing unit', True),
            ('Water Test Report', 'WATER_REPORT', 'Water quality test report from approved lab', True),
            ('Medical Certificates', 'MEDICAL_CERTS', 'Medical fitness certificates for food handlers', False),
        ],
        'FIRE_NOC': [
            ('Layout Plan', 'LAYOUT_PLAN', 'Detailed building layout showing fire exits and safety equipment', True),
            ('Fire Safety Compliance Report', 'FIRE_SAFETY', 'Report from certified fire safety engineer', True),
            ('Property Documents', 'PROPERTY_DOCS', 'Building ownership or NOC from owner', True),
            ('Electrical Safety Certificate', 'ELEC_CERT', 'Electrical safety compliance certificate', False),
        ],
        'POLLUTION_CTO': [
            ('Business Registration', 'BUSINESS_REGISTRATION', 'Certificate of incorporation', True),
            ('Layout Plan', 'LAYOUT_PLAN', 'Detailed layout showing pollution control measures', True),
            ('Environmental Management Plan', 'ENV_PLAN', 'Description of waste management and emission control', True),
            ('Land Documents', 'LAND_DOCS', 'Land ownership or lease documents', True),
        ],
        'FACTORY_LIC': [
            ('PAN Card', 'PAN', 'Business PAN card', True),
            ('Business Registration', 'BUSINESS_REGISTRATION', 'Certificate of incorporation', True),
            ('Layout Plan', 'LAYOUT_PLAN', 'Factory layout plan', True),
            ('Pollution Control Consent', 'POLLUTION_CONSENT', 'Valid consent to operate from PCB', True),
            ('Building Plan Approval', 'BUILD_APPROVAL', 'Approved building plan', False),
            ('Electrical Safety Certificate', 'ELEC_CERT', 'Electrical safety certificate', True),
        ],
        'LABOUR_REG': [
            ('PAN Card', 'PAN', 'Business PAN card', True),
            ('Business Registration', 'BUSINESS_REGISTRATION', 'Certificate of incorporation', True),
            ('Employee List', 'EMPLOYEE_LIST', 'List of all employees with designations', True),
        ],
        'ELEC_SAFETY': [
            ('Electrical Layout Plan', 'ELEC_LAYOUT', 'Detailed electrical wiring diagram', True),
            ('Equipment List', 'EQUIPMENT_LIST', 'List of all electrical machinery and load details', True),
        ],
        'BUILD_PLAN': [
            ('Land Documents', 'LAND_DOCS', 'Land ownership documents or lease', True),
            ('Architectural Plan', 'ARCH_PLAN', 'Approved architectural drawings', True),
            ('Structural Safety Certificate', 'STRUCT_CERT', 'Structural safety certificate from engineer', True),
            ('NOC from Neighbours', 'NEIGHBOUR_NOC', 'No Objection Certificate from adjacent plot owners', False),
        ],
        'HEALTH_NOC': [
            ('PAN Card', 'PAN', 'Business PAN card', True),
            ('FSSAI Licence', 'FSSAI_LIC', 'Valid FSSAI food licence', True),
            ('Medical Certificates', 'MEDICAL_CERTS', 'Health certificates of food handlers', True),
        ],
        'HAZ_MAT': [
            ('Business Registration', 'BUSINESS_REGISTRATION', 'Certificate of incorporation', True),
            ('Hazardous Material List', 'HAZ_LIST', 'Complete list of hazardous materials stored/used', True),
            ('Safety Data Sheets', 'MSDS', 'Material Safety Data Sheets for all chemicals', True),
            ('Storage Facility Plan', 'STORAGE_PLAN', 'Layout of hazardous material storage area', True),
        ],
        'UDYAM': [
            ('PAN Card', 'PAN', 'Proprietor/Company PAN card', True),
            ('Aadhaar Card', 'IDENTITY', 'Proprietor Aadhaar card', True),
        ],
        'PHARMACY_DEMO': [
            ('Drugs Licence Reference', 'DRUGS_LIC', 'Reference to the applicable drugs control licence', True),
            ('Pharmacy Registration', 'PHARMACY_REG', 'Pharmacy registration certificate', True),
            ('Layout Plan', 'LAYOUT_PLAN', 'Pharmacy premises layout showing storage areas', True),
            ('Qualification Certificate', 'QUAL_CERT', 'Qualification certificate of the registered pharmacist', True),
        ],
        'GST_REG': [
            ('PAN Card', 'PAN', 'Business PAN card', True),
            ('Aadhaar Card', 'IDENTITY', 'Proprietor Aadhaar card', True),
            ('Business Address Proof', 'BIZ_ADDRESS', 'Rental agreement or property documents', True),
            ('Bank Account Proof', 'BANK_PROOF', 'Cancelled cheque or bank statement for GST bank verification', True),
        ],
        'SHOPS_EST': [
            ('Business Registration', 'BUSINESS_REGISTRATION', 'Registration certificate or partnership deed', True),
            ('Identity Proof', 'IDENTITY', 'Owner identity proof', True),
            ('Address Proof', 'ADDRESS_PROOF', 'Premises address proof', True),
        ],
    }

    for approval_code, reqs in doc_req_data.items():
        if approval_code in ats:
            for name, code, desc, is_mandatory in reqs:
                dr = DocumentRequirement(
                    id=gen_id(),
                    approval_type_id=ats[approval_code].id,
                    name=name, code=code,
                    description=desc,
                    is_mandatory=is_mandatory
                )
                db.session.add(dr)
    db.session.flush()

    # ===================== USERS =====================
    print("  Creating demo users...")
    users = {}
    demo_password = hash_password('Demo@1234')

    user_data = [
        ('applicant@demo.com', 'Gourav Gadgane', 'APPLICANT', None),
        ('applicant2@demo.com', 'Priya Sharma', 'APPLICANT', None),
        ('inspector@demo.com', 'Arjun Singh', 'OFFICER', None),
        ('admin@demo.com', 'Admin User', 'ADMIN', None),
    ]

    for email, name, role, dept_code in user_data:
        u = User(
            id=gen_id(), email=email, password_hash=demo_password,
            name=name, role=role,
            department_id=depts[dept_code].id if dept_code else None,
            email_verified=True, mobile_verified=True, verification_status='VERIFIED',
        )
        db.session.add(u)
        users[email] = u

    # The AI Compliance Agent is a system background identity. It has no usable
    # password and is entered only through the explicitly-labelled 'AI DEMO'
    # entry point (POST /api/ai-agent/demo-session). It replaces the former
    # human 'Officer' role and co-ordinates the approval lifecycle.
    ai_agent = User(
        id=gen_id(), email='ai-agent@system.demo', name='AI Compliance Agent',
        role='AI_AGENT', password_hash='SYSTEM_ROLE_NOT_A_HUMAN_LOGIN',
        is_active=True, email_verified=True, mobile_verified=True,
        verification_status='VERIFIED',
    )
    db.session.add(ai_agent)
    users['ai-agent@system.demo'] = ai_agent
    db.session.flush()


    # ===================== BUSINESSES (exactly 5) =====================
    print("  Creating demo businesses...")
    business_data = [
        {
            'name': 'Urban Spice Restaurant',
            'owner_email': 'applicant@demo.com',
            'business_type': 'RESTAURANT',
            'sector': 'RESTAURANT',
            'state': 'Maharashtra', 'district': 'Mumbai', 'city': 'Mumbai',
            'address': '12 Bandra West, Near Linking Road, Mumbai - 400050',
            'investment_amount': 3500000, 'employee_count': 22,
            'is_manufacturing': False, 'handles_food': True,
            'involves_construction': False, 'uses_hazardous': False,
            'uses_heavy_machinery': False, 'has_physical_infra': True,
            'env_approval_applicable': False, 'fire_risk': 'MEDIUM',
            'size_category': 'SMALL',
        },
        {
            'name': 'Precision Components Manufacturing',
            'owner_email': 'applicant@demo.com',
            'business_type': 'MANUFACTURING_UNIT',
            'sector': 'MANUFACTURING',
            'state': 'Gujarat', 'district': 'Surat', 'city': 'Surat',
            'address': 'Plot 45, GIDC Industrial Estate, Surat - 395002',
            'investment_amount': 18000000, 'employee_count': 65,
            'is_manufacturing': True, 'handles_food': False,
            'involves_construction': False, 'uses_hazardous': True,
            'uses_heavy_machinery': True, 'has_physical_infra': True,
            'env_approval_applicable': True, 'fire_risk': 'HIGH',
            'size_category': 'LARGE',
        },
        {
            'name': 'CarePlus Pharmacy',
            'owner_email': 'applicant@demo.com',
            'business_type': 'RETAIL_BUSINESS',
            'sector': 'HEALTHCARE',
            'state': 'Tamil Nadu', 'district': 'Chennai', 'city': 'Chennai',
            'address': '78 Anna Nagar East, Chennai - 600040',
            'investment_amount': 4000000, 'employee_count': 8,
            'is_manufacturing': False, 'handles_food': False,
            'involves_construction': False, 'uses_hazardous': False,
            'uses_heavy_machinery': False, 'has_physical_infra': True,
            'env_approval_applicable': False, 'fire_risk': 'MEDIUM',
            'size_category': 'SMALL',
        },
    ]

    businesses = {}
    for bd in business_data:
        owner = users[bd['owner_email']]
        b = Business(
            id=gen_id(), owner_id=owner.id,
            name=bd['name'], owner_name=owner.name,
            business_type=bd['business_type'], sector=bd['sector'],
            state=bd['state'], district=bd['district'], city=bd['city'],
            address=bd['address'],
            investment_amount=bd['investment_amount'],
            employee_count=bd['employee_count'],
            size_category=bd['size_category'],
            is_manufacturing=bd['is_manufacturing'],
            handles_food=bd['handles_food'],
            involves_construction=bd['involves_construction'],
            uses_hazardous=bd['uses_hazardous'],
            uses_heavy_machinery=bd['uses_heavy_machinery'],
            has_physical_infra=bd['has_physical_infra'],
            env_approval_applicable=bd['env_approval_applicable'],
            fire_risk=bd['fire_risk'],
            registration_number=f"BRN-{uuid.uuid4().hex[:8].upper()}",
            status='ACTIVE'
        )
        db.session.add(b)
        businesses[bd['name']] = b
    db.session.flush()

    # ===================== AI DEMO WORKFLOWS =====================
    # Builds every application, inspection, and document for the five demo
    # businesses so the applicant/inspector/admin dashboards and the AI Agent
    # demo share a single source of truth.
    # Licence officer desks are created first so the combined-role demo
    # inspections can be assigned to the proper owning officer.
    from app.services.officer_seed import ensure_officers
    ensure_officers()
    print("  Creating demo workflows...")
    _ensure_demo_workflows()
    db.session.commit()

    # ===================== LICENCE ASSIGNMENTS =====================
    # Persist the sector→licence mapping for every business (DB-driven, derived
    # from the rule engine). create_application will only allow applications for
    # licences assigned here.
    print("  Persisting licence assignments...")
    for business in Business.query.all():
        assign_licences_for_business(business)
    db.session.commit()

    # ===================== CERTIFICATES =====================
    print("  Creating certificates...")
    def create_cert(app):
        if app.status != 'APPROVED':
            return
        at = app.approval_type
        validity_months = at.validity_months or 12
        cert_num = gen_cert_number()
        ver_id = gen_ver_id()
        issue_date = app.decision_date or now() - timedelta(days=5)
        valid_until = issue_date + timedelta(days=validity_months * 30)

        cert = Certificate(
            id=gen_id(), application_id=app.id,
            certificate_number=cert_num,
            business_name=app.business.name,
            applicant_name=app.applicant.name,
            approval_type_name=at.name,
            department_name=app.department.name if app.department else 'DEMO Department',
            issue_date=issue_date,
            valid_until=valid_until,
            verification_id=ver_id,
            qr_data=f"NIRMAN-VERIFY:{cert_num}:{ver_id}",
            is_prototype=True
        )
        db.session.add(cert)
        db.session.flush()

        renewal = Renewal(
            id=gen_id(), certificate_id=cert.id,
            application_id=app.id,
            expiry_date=valid_until,
            status='ACTIVE'
        )
        db.session.add(renewal)

    for business in Business.query.all():
        for app in Application.query.filter_by(business_id=business.id).all():
            create_cert(app)
    db.session.commit()


    # ===================== NOTIFICATIONS =====================
    print("  Creating notifications...")
    notif_data = [
        (users['applicant@demo.com'].id, '✅ Application Submitted', 'Your application for FSSAI Food Licence has been submitted.', 'SUCCESS', None),
        (users['applicant@demo.com'].id, '📋 Inspection Scheduled', f'An inspection for your Fire Safety NOC application is scheduled for {(now() + timedelta(days=1)).strftime("%d %b %Y")}.', 'INFO', None),
        (users['applicant@demo.com'].id, '⚠️ Correction Required', 'Application for Electrical Safety Certificate: Please upload the updated electrical layout plan.', 'WARNING', None),
        (users['applicant@demo.com'].id, '🎉 Application Approved!', 'Congratulations! Your FSSAI Food Licence application has been approved.', 'SUCCESS', None),
        (users['applicant2@demo.com'].id, '🎉 Application Approved!', 'Your Business Registration application has been approved.', 'SUCCESS', None),
        (users['inspector@demo.com'].id, '🏭 Inspection Assigned', 'You have been assigned to inspect a Fire Safety NOC application.', 'INFO', None),
        (users['inspector@demo.com'].id, '✅ Inspection Report Ready', 'An inspection report is ready for AI review.', 'INFO', None),
    ]

    for user_id, title, message, notif_type, app_id in notif_data:
        n = Notification(
            id=gen_id(), user_id=user_id, title=title,
            message=message, type=notif_type,
            related_application_id=app_id
        )
        db.session.add(n)

    # ===================== GRIEVANCES =====================
    print("  Creating grievances...")
    grievances_data = [
        ('applicant@demo.com', 'DELAY', 'My Fire Safety NOC application has been pending for a long time without any update. The SLA is 12 days.', 'UNDER_REVIEW'),
        ('applicant@demo.com', 'DOCUMENT_REJECTION', 'My uploaded electrical layout plan was rejected without clear reason.', 'OPEN'),
        ('applicant2@demo.com', 'OTHER', 'I am unable to log into the system intermittently. Please investigate.', 'RESOLVED'),
    ]

    for email, reason, description, status in grievances_data:
        user = users[email]
        grv_num = f"GRV-2026-{random.randint(1000, 9999)}"
        g = Grievance(
            id=gen_id(), grievance_number=grv_num,
            applicant_id=user.id, reason=reason,
            description=description, status=status,
            resolution='Issue resolved. System has been updated.' if status == 'RESOLVED' else None,
            resolved_by_id=users['admin@demo.com'].id if status == 'RESOLVED' else None
        )
        db.session.add(g)

    # ===================== SCHEMES =====================
    print("  Creating schemes...")
    scheme_data = [
        ('MSME Credit Guarantee Scheme', 'Collateral-free loans up to ₹2 Crore for MSMEs',
         'FOOD_PROCESSING,MANUFACTURING,ELECTRONICS,RETAIL', 'SMALL,MEDIUM',
         'Credit', 'Up to ₹2 Crore collateral-free credit', 'Ministry of MSME'),
        ('PM Kisan Sampada Yojana', 'Support for food processing industries',
         'FOOD_PROCESSING,FOOD_SERVICE,RESTAURANT', 'SMALL,MEDIUM',
         'Grant', '35% subsidy on plant and machinery (max ₹2.5 Crore)', 'Ministry of Food Processing Industries'),
        ('Startup India Seed Fund', 'Early-stage funding for startups',
         'FOOD_PROCESSING,MANUFACTURING,ELECTRONICS,CONSTRUCTION', 'SMALL',
         'Grant', 'Up to ₹20 Lakh seed funding', 'DPIIT, Ministry of Commerce'),
        ('Karnataka Udyog Mitra', 'Single-window facilitation for industries in Karnataka',
         'FOOD_PROCESSING,MANUFACTURING,CONSTRUCTION,ELECTRONICS', 'SMALL,MEDIUM,LARGE',
         'Service', 'Single-window facilitation and fast-track approvals', 'Government of Karnataka'),
        ('Production Linked Incentive (PLI) Scheme', 'Incentives for manufacturers',
         'MANUFACTURING,ELECTRONICS,FOOD_PROCESSING', 'MEDIUM,LARGE',
         'Incentive', '4-6% incentive on incremental sales', 'Ministry of Commerce & Industry'),
        ('Mudra Loan Scheme', 'Loans for micro and small enterprises',
         'FOOD_PROCESSING,RESTAURANT,RETAIL,ELECTRONICS', 'SMALL',
         'Loan', 'Loans from ₹50,000 to ₹10 Lakh', 'SIDBI / Banks'),
    ]

    for name, desc, sectors, sizes, benefit_type, amount, authority in scheme_data:
        s = Scheme(
            id=gen_id(), name=name, description=desc,
            applicable_sectors=sectors, applicable_sizes=sizes,
            benefit_type=benefit_type, amount_description=amount,
            authority=authority
        )
        db.session.add(s)

    db.session.commit()

    # ===================== OFFICERS =====================
    print("  Creating demo licence officers...")
    from app.services.officer_seed import ensure_officers, ensure_officer_assignments
    ensure_officers()
    ensure_officer_assignments()

    # COMBINED ROLE reconciliation: the officer who owns an application is also
    # its inspector. Re-sync every open inspection to the application's assigned
    # officer so review, schedule, inspect, report and decision stay in one desk.
    for app in Application.query.all():
        if app.assigned_officer_id and app.inspections:
            for insp in app.inspections:
                if insp.status not in ('COMPLETED', 'CANCELLED'):
                    insp.inspector_id = app.assigned_officer_id
    db.session.commit()

    print("✅ Database seeded successfully!")
    print("\n📋 DEMO CREDENTIALS:")
    print("  Applicant:            applicant@demo.com / Demo@1234")
    print("  Admin:                admin@demo.com / Demo@1234")
    print("  Licence Officer / Inspector: inspector@demo.com / Demo@1234 — Arjun Singh")
    print("  AI Agent:  system role (enter via the 'AI DEMO' button in the app)")
    print("\n⚠️  All data is DEMO/PROTOTYPE data for SIH presentation only.")
    print("    The Licence Officer is a DEMO ACCOUNT — NOT A REAL\n    GOVERNMENT ACCOUNT.")


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
        seed()
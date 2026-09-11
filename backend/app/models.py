from . import db
from datetime import datetime, timezone
import uuid

def gen_id():
    return str(uuid.uuid4())

def now():
    return datetime.now(timezone.utc)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    # Roles: APPLICANT, INSPECTOR, ADMIN, OFFICER, and the system role AI_AGENT.
    # OFFICER = licence approving officer (separate login from applicant pool,
    # created by demo seeding, not self-registerable). AI_AGENT is a background
    # system identity (created by seed/system), not a human login.
    role = db.Column(db.String(50), nullable=False, default='APPLICANT')
    phone = db.Column(db.String(20), unique=True)
    department_id = db.Column(db.String(36), db.ForeignKey('departments.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    # Verification & OTP metadata. OTPs are stored ONLY as a keyed digest, never
    # as plain text. verification_status: UNVERIFIED -> VERIFIED.
    email_verified = db.Column(db.Boolean, nullable=False, default=False, server_default='0')
    mobile_verified = db.Column(db.Boolean, nullable=False, default=False, server_default='0')
    verification_status = db.Column(db.String(20), nullable=False, default='UNVERIFIED', server_default='UNVERIFIED')
    otp_hash = db.Column(db.String(128))
    otp_expires_at = db.Column(db.DateTime)
    otp_attempts = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    otp_resends = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    otp_last_sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=now)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)

    businesses = db.relationship('Business', backref='owner', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)
    grievances = db.relationship('Grievance', foreign_keys='Grievance.applicant_id', backref='applicant', lazy=True)

    @property
    def is_verified(self):
        return self.verification_status == 'VERIFIED'

    def mark_verified(self):
        self.email_verified = True
        self.mobile_verified = True
        self.verification_status = 'VERIFIED'
        self.otp_hash = None
        self.otp_expires_at = None
        self.otp_attempts = 0
        self.otp_resends = 0
        self.otp_last_sent_at = None

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'role': self.role,
            'phone': self.phone,
            'department_id': self.department_id,
            'email_verified': self.email_verified,
            'mobile_verified': self.mobile_verified,
            'verification_status': self.verification_status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_demo = db.Column(db.Boolean, default=True)
    avg_processing_days = db.Column(db.Integer, default=10)
    sla_days = db.Column(db.Integer, default=15)
    created_at = db.Column(db.DateTime, default=now)

    approval_types = db.relationship('ApprovalType', backref='department', lazy=True)
    applications = db.relationship('Application', backref='department', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'is_demo': self.is_demo,
            'avg_processing_days': self.avg_processing_days,
            'sla_days': self.sla_days
        }

class Sector(db.Model):
    """Reference table of the sectors a business can declare.

    Mirrors the frontend registration wizard's sector list so the DB has a
    single, queryable source for sector-derived licence assignment. A business
    stores its sector by code on Business.sector.
    """
    __tablename__ = 'sectors'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    code = db.Column(db.String(100), unique=True, nullable=False)
    label = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now)

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'label': self.label,
            'is_active': self.is_active
        }


class ApprovalType(db.Model):
    __tablename__ = 'approval_types'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    department_id = db.Column(db.String(36), db.ForeignKey('departments.id'), nullable=False)
    description = db.Column(db.Text)
    why_required = db.Column(db.Text)
    requires_inspection = db.Column(db.Boolean, default=False)
    estimated_days = db.Column(db.Integer, default=10)
    sla_days = db.Column(db.Integer, default=15)
    validity_months = db.Column(db.Integer, default=12)
    workflow_type = db.Column(db.String(20), default='A')  # A=simple, B=inspection, C=correction
    official_sources = db.Column(db.Text, default='[]')    # JSON array of official source objects
    reference_url = db.Column(db.Text)                     # Primary official reference URL
    priority = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=now)

    document_requirements = db.relationship('DocumentRequirement', backref='approval_type', lazy=True)
    applications = db.relationship('Application', backref='approval_type', lazy=True)

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'department_id': self.department_id,
            'department': self.department.to_dict() if self.department else None,
            'description': self.description,
            'why_required': self.why_required,
            'official_sources': json.loads(self.official_sources or '[]'),
            'reference_url': self.reference_url,
            'requires_inspection': self.requires_inspection,
            'estimated_days': self.estimated_days,
            'sla_days': self.sla_days,
            'validity_months': self.validity_months,
            'workflow_type': self.workflow_type,
            'priority': self.priority,
            'document_requirements': [dr.to_dict() for dr in self.document_requirements]
        }

class ApprovalRule(db.Model):
    __tablename__ = 'approval_rules'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    approval_type_id = db.Column(db.String(36), db.ForeignKey('approval_types.id'), nullable=False)
    condition_field = db.Column(db.String(100), nullable=False)  # e.g. 'sector', 'handles_food'
    condition_operator = db.Column(db.String(20), nullable=False)  # eq, in, gte, lte, true
    condition_value = db.Column(db.String(500))
    is_mandatory = db.Column(db.Boolean, default=True)

    approval_type = db.relationship('ApprovalType')

    def to_dict(self):
        return {
            'id': self.id,
            'approval_type_id': self.approval_type_id,
            'condition_field': self.condition_field,
            'condition_operator': self.condition_operator,
            'condition_value': self.condition_value,
            'is_mandatory': self.is_mandatory
        }

class DocumentRequirement(db.Model):
    __tablename__ = 'document_requirements'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    approval_type_id = db.Column(db.String(36), db.ForeignKey('approval_types.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_mandatory = db.Column(db.Boolean, default=True)
    allowed_formats = db.Column(db.String(200), default='pdf,jpg,png')
    max_size_mb = db.Column(db.Integer, default=5)

    def to_dict(self):
        return {
            'id': self.id,
            'approval_type_id': self.approval_type_id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'is_mandatory': self.is_mandatory,
            'allowed_formats': self.allowed_formats.split(',') if self.allowed_formats else [],
            'max_size_mb': self.max_size_mb
        }

class Business(db.Model):
    __tablename__ = 'businesses'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    owner_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    owner_name = db.Column(db.String(255), nullable=False)
    business_type = db.Column(db.String(100), nullable=False)
    sector = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    district = db.Column(db.String(100))
    city = db.Column(db.String(100))
    address = db.Column(db.Text)
    investment_amount = db.Column(db.Float, default=0)
    employee_count = db.Column(db.Integer, default=0)
    size_category = db.Column(db.String(20), default='SMALL')  # SMALL, MEDIUM, LARGE
    # Operation flags
    is_manufacturing = db.Column(db.Boolean, default=False)
    handles_food = db.Column(db.Boolean, default=False)
    involves_construction = db.Column(db.Boolean, default=False)
    uses_hazardous = db.Column(db.Boolean, default=False)
    uses_heavy_machinery = db.Column(db.Boolean, default=False)
    has_physical_infra = db.Column(db.Boolean, default=True)
    env_approval_applicable = db.Column(db.Boolean, default=False)
    fire_risk = db.Column(db.String(20), default='LOW')  # LOW, MEDIUM, HIGH
    status = db.Column(db.String(50), default='ACTIVE')
    registration_number = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=now)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)

    applications = db.relationship('Application', backref='business', lazy=True)
    licence_assignments = db.relationship('BusinessLicenceAssignment', lazy=True, back_populates='business', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'owner_id': self.owner_id,
            'name': self.name,
            'owner_name': self.owner_name,
            'business_type': self.business_type,
            'sector': self.sector,
            'state': self.state,
            'district': self.district,
            'city': self.city,
            'address': self.address,
            'investment_amount': self.investment_amount,
            'employee_count': self.employee_count,
            'size_category': self.size_category,
            'is_manufacturing': self.is_manufacturing,
            'handles_food': self.handles_food,
            'involves_construction': self.involves_construction,
            'uses_hazardous': self.uses_hazardous,
            'uses_heavy_machinery': self.uses_heavy_machinery,
            'has_physical_infra': self.has_physical_infra,
            'env_approval_applicable': self.env_approval_applicable,
            'fire_risk': self.fire_risk,
            'status': self.status,
            'registration_number': self.registration_number,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class BusinessLicenceAssignment(db.Model):
    """Persisted sector→licence assignment for a business.

    Written server-side at registration (and backfilled for demo businesses)
    from the rule engine (approval_engine.generate_approval_checklist), so the
    licence mapping lives in SQLite — not in UI logic. create_application
    refuses any licence that is not in this business's assigned set.
    """
    __tablename__ = 'business_licence_assignments'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    business_id = db.Column(db.String(36), db.ForeignKey('businesses.id'), nullable=False, index=True)
    approval_type_id = db.Column(db.String(36), db.ForeignKey('approval_types.id'), nullable=False)
    is_mandatory = db.Column(db.Boolean, default=True)
    why_triggered = db.Column(db.Text)
    assigned_at = db.Column(db.DateTime, default=now)

    business = db.relationship('Business', back_populates='licence_assignments', foreign_keys=[business_id])
    approval_type = db.relationship('ApprovalType', foreign_keys=[approval_type_id])

    def to_dict(self):
        return {
            'id': self.id,
            'business_id': self.business_id,
            'approval_type_id': self.approval_type_id,
            'approval_type_code': self.approval_type.code if self.approval_type else None,
            'approval_type_name': self.approval_type.name if self.approval_type else None,
            'is_mandatory': self.is_mandatory,
            'why_triggered': self.why_triggered,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None
        }

class Application(db.Model):
    __tablename__ = 'applications'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    application_number = db.Column(db.String(50), unique=True, nullable=False)
    business_id = db.Column(db.String(36), db.ForeignKey('businesses.id'), nullable=False)
    approval_type_id = db.Column(db.String(36), db.ForeignKey('approval_types.id'), nullable=False)
    department_id = db.Column(db.String(36), db.ForeignKey('departments.id'), nullable=True)
    applicant_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    # Legacy field kept for backwards compatibility with older demo databases.
    assigned_officer_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    # AI Compliance Agent driven fields.
    risk_score = db.Column(db.Integer, default=0)
    risk_level = db.Column(db.String(20), default='LOW')          # LOW, MEDIUM, HIGH
    ai_decision = db.Column(db.String(20))                        # APPROVE, REJECT, CLARIFY
    ai_decision_confidence = db.Column(db.Integer, default=0)     # 0-100
    ai_decision_summary = db.Column(db.Text)
    ai_decision_rules = db.Column(db.Text)                        # JSON list of evaluated rules
    ai_reviewed_at = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='DRAFT')
    # DRAFT, AI_PROCESSING, AI_CHECK_COMPLETE, SUBMITTED_TO_AUTHORITY,
    # ASSIGNED_TO_OFFICER, SUBMITTED, UNDER_REVIEW, CORRECTION_REQUIRED,
    # INSPECTION_REQUIRED, INSPECTION_SCHEDULED, INSPECTION_COMPLETED,
    # INSPECTION_PASSED, DECISION_PENDING, APPROVED, REJECTED, EXPIRED, RENEWAL_REQUIRED
    # ADDITIONAL_DOCUMENTS_REQUIRED, DOCUMENT_VALIDATION — officer asked applicant for more documents.

    # --- State machine: only these transitions are allowed ---
    VALID_TRANSITIONS = {
        'DRAFT':                 ['SUBMITTED'],
        'AI_PROCESSING':         ['AI_CHECK_COMPLETE'],
        'AI_CHECK_COMPLETE':     ['SUBMITTED_TO_AUTHORITY'],
        'SUBMITTED_TO_AUTHORITY': ['ASSIGNED_TO_OFFICER'],
        'ASSIGNED_TO_OFFICER':   ['DOCUMENT_VALIDATION', 'SUBMITTED', 'UNDER_REVIEW'],
        'SUBMITTED':             ['DOCUMENT_VALIDATION', 'UNDER_REVIEW'],
        'DOCUMENT_VALIDATION':   ['UNDER_REVIEW', 'NEEDS_CORRECTION', 'ADDITIONAL_DOCUMENTS_REQUIRED'],
        'CORRECTION_REQUIRED':   ['SUBMITTED', 'DOCUMENT_VALIDATION', 'ADDITIONAL_DOCUMENTS_REQUIRED'],
        'NEEDS_CORRECTION':      ['SUBMITTED'],
        'ADDITIONAL_DOCUMENTS_REQUIRED': ['DOCUMENT_VALIDATION'],
        'UNDER_REVIEW':          ['INSPECTION_REQUIRED', 'DECISION_PENDING', 'ADDITIONAL_DOCUMENTS_REQUIRED'],
        'DECISION_PENDING':      ['INSPECTION_REQUIRED', 'APPROVED', 'REJECTED', 'ADDITIONAL_DOCUMENTS_REQUIRED'],
        'INSPECTION_REQUIRED':   ['INSPECTION_SCHEDULED'],
        'INSPECTION_SCHEDULED':  ['IN_PROGRESS', 'INSPECTION_COMPLETED'],
        'IN_PROGRESS':           ['INSPECTION_COMPLETED', 'INSPECTION_SCHEDULED'],
        'INSPECTION_COMPLETED':  ['INSPECTION_PASSED', 'DECISION_PENDING', 'APPROVED', 'REJECTED', 'ADDITIONAL_DOCUMENTS_REQUIRED'],
        'INSPECTION_PASSED':     ['APPROVED', 'REJECTED', 'ADDITIONAL_DOCUMENTS_REQUIRED'],
        'APPROVED':              ['RENEWAL_REQUIRED'],
        'REJECTED':              [],
        'EXPIRED':               [],
        'RENEWAL_REQUIRED':      [],
    }
    submission_date = db.Column(db.DateTime)
    decision_date = db.Column(db.DateTime)
    sla_deadline = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    rejection_reason = db.Column(db.Text)
    correction_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)

    applicant = db.relationship('User', foreign_keys=[applicant_id], backref='applications')
    assigned_officer = db.relationship('User', foreign_keys=[assigned_officer_id])
    # Active officer routing record (application_assignments). DB is the source
    # of truth for which licence officer currently owns this application.
    assignment = db.relationship('ApplicationAssignment', backref='application', uselist=False, cascade='all, delete-orphan')
    status_history = db.relationship('ApplicationStatusHistory', backref='application', lazy=True, order_by='ApplicationStatusHistory.created_at')
    documents = db.relationship('Document', backref='application', lazy=True)
    inspections = db.relationship('Inspection', backref='application', lazy=True)
    certificate = db.relationship('Certificate', backref='application', uselist=False)
    audit_logs = db.relationship('AuditLog', backref='application', lazy=True, order_by='AuditLog.created_at')

    def can_transition_to(self, new_status):
        """Return True if transitioning from self.status to new_status is valid."""
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    def transition_to(self, new_status):
        """Apply the transition and set the new status. Raises ValueError if invalid."""
        if not self.can_transition_to(new_status):
            raise ValueError(
                f'Invalid status transition: {self.status} -> {new_status}. '
                f'Allowed: {self.VALID_TRANSITIONS.get(self.status, [])}'
            )
        self.status = new_status

    def to_dict(self, include_details=False):
        data = {
            'id': self.id,
            'application_number': self.application_number,
            'business_id': self.business_id,
            'business_name': self.business.name if self.business else None,
            'approval_type_id': self.approval_type_id,
            'approval_type_name': self.approval_type.name if self.approval_type else None,
            'approval_type_code': self.approval_type.code if self.approval_type else None,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'applicant_id': self.applicant_id,
            'applicant_name': self.applicant.name if self.applicant else None,
            'assigned_officer_id': self.assigned_officer_id,
            'assigned_officer_name': self.assigned_officer.name if self.assigned_officer else None,
            'assignment': application_assignment_to_dict(self),
            'risk_score': self.risk_score,
            'risk_level': self.risk_level,
            'ai_decision': self.ai_decision,
            'ai_decision_confidence': self.ai_decision_confidence,
            'ai_decision_summary': self.ai_decision_summary,
            'ai_reviewed_at': self.ai_reviewed_at.isoformat() if self.ai_reviewed_at else None,
            'status': self.status,
            'submission_date': self.submission_date.isoformat() if self.submission_date else None,
            'decision_date': self.decision_date.isoformat() if self.decision_date else None,
            'sla_deadline': self.sla_deadline.isoformat() if self.sla_deadline else None,
            'notes': self.notes,
            'rejection_reason': self.rejection_reason,
            'correction_notes': self.correction_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_details:
            data['status_history'] = [s.to_dict() for s in self.status_history]
            data['documents'] = [d.to_dict() for d in self.documents]
            data['inspections'] = [i.to_dict() for i in self.inspections]
            data['audit_logs'] = [a.to_dict() for a in self.audit_logs]
            data['approval_type'] = self.approval_type.to_dict() if self.approval_type else None
            data['certificate'] = self.certificate.to_dict() if self.certificate else None
            data['business'] = self.business.to_dict() if self.business else None
        return data

class ApplicationStatusHistory(db.Model):
    __tablename__ = 'application_status_history'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    application_id = db.Column(db.String(36), db.ForeignKey('applications.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    changed_by_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now)

    changed_by = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'application_id': self.application_id,
            'status': self.status,
            'changed_by_id': self.changed_by_id,
            'changed_by_name': self.changed_by.name if self.changed_by else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    application_id = db.Column(db.String(36), db.ForeignKey('applications.id'), nullable=False)
    business_id = db.Column(db.String(36), db.ForeignKey('businesses.id'))
    requirement_id = db.Column(db.String(36), db.ForeignKey('document_requirements.id'))
    uploader_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    filename = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(500), nullable=False)
    doc_type = db.Column(db.String(100))
    file_path = db.Column(db.String(1000))
    file_size = db.Column(db.Integer)
    mime_type = db.Column(db.String(100))
    status = db.Column(db.String(50), default='UPLOADED')  # UPLOADED, APPROVED, REJECTED, VERIFIED (legacy)
    ocr_text = db.Column(db.Text)
    ocr_data = db.Column(db.Text)  # JSON
    # Every re-upload of the same requirement is a NEW record with an
    # incremented version — the officer reviews the latest version, earlier
    # versions remain as an audit trail.
    document_version = db.Column(db.Integer, default=1)
    # Per-document verification state. Every required document carries its own
    # independent status:
    #   VALIDATION_PENDING    → file received, automated checks running
    #   UNDER_OFFICER_REVIEW  → automated checks passed, awaiting the officer
    #   RESUBMISSION_REQUIRED → automated checks flagged it (or officer asked
    #                           for a specific corrective upload)
    #   APPROVED / REJECTED   → individual officer verdict (with reason)
    #   VERIFIED              → legacy seeded rows / verify-once reuses
    # (NEEDS_CORRECTION is a legacy alias kept for old rows.) Approving or
    # rejecting one document NEVER changes the state of any other document.
    verification_status = db.Column(db.String(50), default='UPLOADED')
    verification_notes = db.Column(db.Text)
    # Accountability for who/when a document was reviewed and, when rejected,
    # the exact reason the applicant must fix.
    verified_by_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    rejection_reason = db.Column(db.Text)
    expiry_date = db.Column(db.DateTime)
    uploaded_at = db.Column(db.DateTime, default=now)
    verified_at = db.Column(db.DateTime)

    uploader = db.relationship('User', foreign_keys=[uploader_id])
    verified_by = db.relationship('User', foreign_keys=[verified_by_id])
    requirement = db.relationship('DocumentRequirement')
    business = db.relationship('Business')

    def to_dict(self):
        return {
            'id': self.id,
            'application_id': self.application_id,
            'business_id': self.business_id,
            'business_name': self.business.name if self.business else None,
            'requirement_id': self.requirement_id,
            'requirement_name': self.requirement.name if self.requirement else self.doc_type,
            'filename': self.original_filename,
            'original_filename': self.original_filename,
            'doc_type': self.doc_type,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'status': self.status,
            'ocr_text': self.ocr_text,
            'ocr_data': self.ocr_data,
            'verification_status': self.verification_status,
            'verification_notes': self.verification_notes,
            'document_version': self.document_version,
            'rejection_reason': self.rejection_reason,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'uploader_id': self.uploader_id,
            'uploader_name': self.uploader.name if self.uploader else None,
            'verified_by_id': self.verified_by_id,
            'verified_by_name': self.verified_by.name if self.verified_by else None
        }

class Inspection(db.Model):
    __tablename__ = 'inspections'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    application_id = db.Column(db.String(36), db.ForeignKey('applications.id'), nullable=False)
    inspector_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    assigned_by_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    scheduled_date = db.Column(db.DateTime)
    completed_date = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='PENDING')
    # PENDING, ASSIGNED, SCHEDULED, STARTED, COMPLETED, CANCELLED
    checklist_data = db.Column(db.Text)  # JSON
    remarks = db.Column(db.Text)
    recommendation = db.Column(db.String(50))  # APPROVE, REJECT, CORRECTION
    overall_result = db.Column(db.String(50))  # PASS, FAIL, CONDITIONAL
    decision_reason = db.Column(db.Text)
    report_submitted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=now)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)

    inspector = db.relationship('User', foreign_keys=[inspector_id])
    assigned_by = db.relationship('User', foreign_keys=[assigned_by_id])
    evidence = db.relationship('InspectionEvidence', backref='inspection', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'application_id': self.application_id,
            'inspector_id': self.inspector_id,
            'inspector_name': self.inspector.name if self.inspector else None,
            'assigned_by_id': self.assigned_by_id,
            'scheduled_date': self.scheduled_date.isoformat() if self.scheduled_date else None,
            'completed_date': self.completed_date.isoformat() if self.completed_date else None,
            'status': self.status,
            'checklist_data': self.checklist_data,
            'remarks': self.remarks,
            'recommendation': self.recommendation,
            'overall_result': self.overall_result,
            'decision_reason': self.decision_reason,
            'report_submitted_at': self.report_submitted_at.isoformat() if self.report_submitted_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'evidence': [e.to_dict() for e in self.evidence]
        }

class InspectionEvidence(db.Model):
    __tablename__ = 'inspection_evidence'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    inspection_id = db.Column(db.String(36), db.ForeignKey('inspections.id'), nullable=False)
    filename = db.Column(db.String(500))
    original_filename = db.Column(db.String(500))
    file_path = db.Column(db.String(1000))
    caption = db.Column(db.String(500))
    uploaded_at = db.Column(db.DateTime, default=now)

    def to_dict(self):
        return {
            'id': self.id,
            'inspection_id': self.inspection_id,
            'filename': self.original_filename,
            'caption': self.caption,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }

class Certificate(db.Model):
    __tablename__ = 'certificates'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    application_id = db.Column(db.String(36), db.ForeignKey('applications.id'), nullable=False)
    certificate_number = db.Column(db.String(100), unique=True, nullable=False)
    business_name = db.Column(db.String(255))
    applicant_name = db.Column(db.String(255))
    approval_type_name = db.Column(db.String(255))
    department_name = db.Column(db.String(255))
    issue_date = db.Column(db.DateTime, default=now)
    valid_until = db.Column(db.DateTime)
    verification_id = db.Column(db.String(100), unique=True)
    is_prototype = db.Column(db.Boolean, default=True)
    qr_data = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now)

    renewal = db.relationship('Renewal', backref='certificate', uselist=False)

    def to_dict(self):
        return {
            'id': self.id,
            'application_id': self.application_id,
            'certificate_number': self.certificate_number,
            'business_name': self.business_name,
            'applicant_name': self.applicant_name,
            'approval_type_name': self.approval_type_name,
            'department_name': self.department_name,
            'issue_date': self.issue_date.isoformat() if self.issue_date else None,
            'valid_until': self.valid_until.isoformat() if self.valid_until else None,
            'verification_id': self.verification_id,
            'is_prototype': self.is_prototype,
            'qr_data': self.qr_data
        }

class Renewal(db.Model):
    __tablename__ = 'renewals'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    certificate_id = db.Column(db.String(36), db.ForeignKey('certificates.id'), nullable=False)
    application_id = db.Column(db.String(36), db.ForeignKey('applications.id'))
    status = db.Column(db.String(50), default='PENDING')
    expiry_date = db.Column(db.DateTime)
    reminder_sent_60 = db.Column(db.Boolean, default=False)
    reminder_sent_30 = db.Column(db.Boolean, default=False)
    reminder_sent_7 = db.Column(db.Boolean, default=False)
    renewed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=now)

    def to_dict(self):
        return {
            'id': self.id,
            'certificate_id': self.certificate_id,
            'application_id': self.application_id,
            'status': self.status,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), default='INFO')  # INFO, SUCCESS, WARNING, ERROR
    is_read = db.Column(db.Boolean, default=False)
    related_application_id = db.Column(db.String(36))
    created_at = db.Column(db.DateTime, default=now)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'is_read': self.is_read,
            'related_application_id': self.related_application_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Grievance(db.Model):
    __tablename__ = 'grievances'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    grievance_number = db.Column(db.String(50), unique=True)
    applicant_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    application_id = db.Column(db.String(36), db.ForeignKey('applications.id'))
    reason = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='OPEN')  # OPEN, UNDER_REVIEW, RESOLVED, CLOSED
    resolution = db.Column(db.Text)
    resolved_by_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=now)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)

    resolved_by = db.relationship('User', foreign_keys=[resolved_by_id])

    def to_dict(self):
        return {
            'id': self.id,
            'grievance_number': self.grievance_number,
            'applicant_id': self.applicant_id,
            'applicant_name': self.applicant.name if self.applicant else None,
            'application_id': self.application_id,
            'reason': self.reason,
            'description': self.description,
            'status': self.status,
            'resolution': self.resolution,
            'resolved_by_name': self.resolved_by.name if self.resolved_by else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    application_id = db.Column(db.String(36), db.ForeignKey('applications.id'))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    action = db.Column(db.String(200), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=now)

    user = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'application_id': self.application_id,
            'user_id': self.user_id,
            'user_name': self.user.name if self.user else None,
            'action': self.action,
            'details': self.details,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Officer(db.Model):
    __tablename__ = 'officers'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    officer_number = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), unique=True, nullable=False)
    designation = db.Column(db.String(255), nullable=False)
    authority = db.Column(db.String(255), nullable=False)
    department_id = db.Column(db.String(36), db.ForeignKey('departments.id'), nullable=True)
    location = db.Column(db.String(100))          # city
    state = db.Column(db.String(100))
    # Short note displayed to applicants and on the officer's own dashboard.
    is_demo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now)

    user = db.relationship('User', backref='officer_profile')
    department = db.relationship('Department', backref='officers')
    # Licence types this officer is authorised to process.
    licence_types = db.relationship('OfficerLicence', backref='officer', lazy=True,
                                    cascade='all, delete-orphan')

    def licence_type_ids(self):
        return [ol.approval_type_id for ol in self.licence_types]

    def to_dict(self):
        return {
            'id': self.id,
            'officer_number': self.officer_number,
            'user_id': self.user_id,
            'name': self.user.name if self.user else None,
            'email': self.user.email if self.user else None,
            'phone': self.user.phone if self.user else None,
            'designation': self.designation,
            'authority': self.authority,
            'department_id': self.department_id,
            'department_name': self.department.name if self.department else None,
            'location': self.location,
            'state': self.state,
            'is_demo': self.is_demo,
            'licence_codes': [ol.approval_type.code if ol.approval_type else None
                              for ol in self.licence_types if ol.approval_type],
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class OfficerLicence(db.Model):
    __tablename__ = 'officer_licences'
    __table_args__ = (db.UniqueConstraint('officer_id', 'approval_type_id', name='uq_officer_licence'),)
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    officer_id = db.Column(db.String(36), db.ForeignKey('officers.id'), nullable=False)
    approval_type_id = db.Column(db.String(36), db.ForeignKey('approval_types.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=now)

    approval_type = db.relationship('ApprovalType')

    def to_dict(self):
        return {
            'id': self.id,
            'officer_id': self.officer_id,
            'approval_type_id': self.approval_type_id,
            'approval_type_code': self.approval_type.code if self.approval_type else None,
            'approval_type_name': self.approval_type.name if self.approval_type else None
        }

class ApplicationAssignment(db.Model):
    __tablename__ = 'application_assignments'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    application_id = db.Column(db.String(36), db.ForeignKey('applications.id'), unique=True, nullable=False)
    # officer_id points at the User row with role == 'OFFICER'.
    officer_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    assigned_by_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    auto_routed = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(20), default='ACTIVE')  # ACTIVE, REASSIGNED, CLOSED
    # Officer decision on this assignment (persisted for audit).
    decision = db.Column(db.String(50))  # APPROVED, REJECTED, ADDITIONAL_DOCUMENTS, INSPECTION_REQUIRED
    decision_notes = db.Column(db.Text)
    decided_at = db.Column(db.DateTime)
    assigned_at = db.Column(db.DateTime, default=now)

    officer = db.relationship('User', foreign_keys=[officer_id])
    assigned_by = db.relationship('User', foreign_keys=[assigned_by_id])

    def to_dict(self):
        officer_profile = Officer.query.filter_by(user_id=self.officer_id).first()
        return {
            'id': self.id,
            'application_id': self.application_id,
            'officer_id': self.officer_id,
            'officer_name': self.officer.name if self.officer else None,
            'officer_email': self.officer.email if self.officer else None,
            'officer_designation': officer_profile.designation if officer_profile else None,
            'officer_authority': officer_profile.authority if officer_profile else None,
            'officer_location': officer_profile.location if officer_profile else None,
            'assigned_by_id': self.assigned_by_id,
            'assigned_by_name': self.assigned_by.name if self.assigned_by else None,
            'auto_routed': self.auto_routed,
            'status': self.status,
            'decision': self.decision,
            'decision_notes': self.decision_notes,
            'decided_at': self.decided_at.isoformat() if self.decided_at else None,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None
        }

def application_assignment_to_dict(app):
    if not app.assignment:
        return None
    return app.assignment.to_dict()

class Scheme(db.Model):
    __tablename__ = 'schemes'
    id = db.Column(db.String(36), primary_key=True, default=gen_id)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    applicable_sectors = db.Column(db.String(500))  # comma-separated
    applicable_sizes = db.Column(db.String(200))
    benefit_type = db.Column(db.String(100))
    amount_description = db.Column(db.String(200))
    authority = db.Column(db.String(200))
    is_demo = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'applicable_sectors': self.applicable_sectors.split(',') if self.applicable_sectors else [],
            'applicable_sizes': self.applicable_sizes.split(',') if self.applicable_sizes else [],
            'benefit_type': self.benefit_type,
            'amount_description': self.amount_description,
            'authority': self.authority,
            'is_demo': self.is_demo
        }

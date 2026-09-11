from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models import Document, DocumentRequirement, Application, ApplicationStatusHistory, User, AuditLog, Notification, Business
from ..services import ai_decision_service
from ..services.realtime import publish
from ..services.ocr_service import process_document_ocr
import os, uuid, json, shutil
from werkzeug.utils import secure_filename
from datetime import datetime, timezone

documents_bp = Blueprint('documents', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_current_user():
    """Delegate to the shared 401-safe helper (no silent None)."""
    from .utils import get_current_user as _shared
    return _shared()

def now():
    return datetime.now(timezone.utc)


# --- Layered document validation ------------------------------------------
# Documents are screened in layers. NO layer claims borderline authenticity:
# automated checks only triage — the licence officer is the accountable
# verifier. Official verification is only ever reported as REQUIRED/PENDING,
# never as performed, unless a real government source is integrated.

def _mask_sensitive(text):
    """Mask Aadhaar-style 12-digit numbers in any stored OCR text/fields."""
    if not text:
        return text
    import re
    masked = re.sub(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', 'XXXX XXXX XXXX', text)
    # Also mask any other bare 12-digit runs (whitespace/newline variants).
    return re.sub(r'\b\d{12}\b', 'XXXX XXXX XXXX', masked)


def _mask_fields(fields):
    """Mask sensitive identity fields before they are stored (minimization)."""
    masked = dict(fields or {})
    for key in ('aadhar_number', 'aadhaar_number', 'uidai_number'):
        if masked.get(key):
            masked[key] = 'XXXX XXXX XXXX'
    return masked


def _file_checks(doc, requirement):
    """Layer 1 — file-level triage (existence, size, extension, MIME hint)."""
    issues = []
    ext = (doc.original_filename or '').rsplit('.', 1)[-1].lower() if '.' in (doc.original_filename or '') else 'bin'
    allowed = (requirement.allowed_formats or 'pdf,jpg,png').replace(' ', '').split(',')
    allowed = [a.lower() for a in allowed if a]
    if allowed and ext not in allowed:
        issues.append(f'extension "{ext}" is not in the allowed formats ({", ".join(allowed)})')
    max_mb = (requirement.max_size_mb or 5) if requirement else 5
    if doc.file_size and max_mb and doc.file_size > max_mb * 1024 * 1024:
        issues.append(f'file exceeds the {max_mb}MB limit for this requirement')
    readable = bool(doc.file_path and os.path.exists(doc.file_path) and doc.file_size)
    if not readable:
        issues.append('stored file could not be read')
    return {
        'status': 'fail' if issues else 'pass',
        'extension': ext,
        'mime_type': doc.mime_type,
        'size_bytes': doc.file_size,
        'max_size_mb': max_mb,
        'readable': readable,
        'issues': issues,
    }


def _content_checks(doc_type, fields, confidence):
    """Layer 2 — extracted-content plausibility (masked), never authenticity."""
    required_by_type = {
        'PAN': ['pan_number', 'name'],
        'IDENTITY': ['name', 'aadhar_number'],
        'BUSINESS_REGISTRATION': ['cin', 'incorporation_date'],
        'FIRE_SAFETY': ['premises'],
        'LAYOUT_PLAN': ['approval_number'],
    }
    required = required_by_type.get((doc_type or '').upper(), [])
    missing = [f for f in required if not (fields or {}).get(f)]
    return {
        'status': 'fail' if missing else 'pass',
        'required_fields_present': len(required) - len(missing),
        'required_fields_total': len(required),
        'missing_fields': missing,
        'confidence': confidence,
        'extracted_fields_masked': fields or {},
    }


def _tamper_checks(doc, text, doc_type):
    """Layer 3 — tamper/forgery triage indicators (heuristic, non-authoritative).

    FLAGGED here never auto-rejects a document; it simply keeps the document
    in UNDER_OFFICER_REVIEW so a human decides.
    """
    import re
    indicators = []
    hay = (text or '').upper()
    for marker in ['DEMO DOCUMENT', 'SAMPLE ONLY', 'NOT REAL', 'FAKE', 'PHOTOSHOP',
                   'ILLUSTRATIVE SAMPLE', 'FOR DEMONSTRATION ONLY']:
        if marker in hay:
            indicators.append(f'text contains placeholder marker "{marker}"')
    if (doc.mime_type or '').startswith('text/') and (doc_type or '').upper() in ('PAN', 'IDENTITY'):
        indicators.append('identity document uploaded as plain text')
    aadhaar_runs = re.findall(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', hay)
    if aadhaar_runs and (doc_type or '').upper() in ('PAN', 'IDENTITY'):
        # Presence of Aadhaar-style number is expected for IDENTITY; note count.
        indicators.append(f'contains {len(aadhaar_runs)} Aadhaar-style sequence(s) — masked in storage')
    return {'status': 'flag' if indicators else 'pass', 'indicators': indicators}


def run_demo_prevalidation(doc, application, user):
    """Deterministic, transparent pre-validation (layered, no false claims).

    Status transitions:
      upload -> VALIDATION_PENDING -> (checks) -> UNDER_OFFICER_REVIEW
                                             or -> RESUBMISSION_REQUIRED
    The demo deterministically flags an initial address document unless the
    applicant uploads a corrected/verified version, so the SIH demo shows a
    real correction -> revalidation path while staying explicit about being
    simulated.
    """
    filename = (doc.original_filename or '').lower()
    doc_label = (doc.doc_type or '').upper()
    requirement = DocumentRequirement.query.get(doc.requirement_id) if doc.requirement_id else None
    address_document = 'ADDRESS' in doc_label or 'address' in filename
    corrected = any(marker in filename for marker in ['corrected', 'verified', 'fixed', 'v2'])

    # Layer 1 — file triage.
    file_checks = _file_checks(doc, requirement)
    # Layer 2 — content plausibility from masked OCR fields.
    try:
        fields = json.loads(doc.ocr_data or '{}')
    except (ValueError, TypeError):
        fields = {}
    content_checks = _content_checks(doc.doc_type, fields, 0.0)
    # Layer 3 — tamper triage.
    tamper_checks = _tamper_checks(doc, doc.ocr_text, doc.doc_type)

    flags = []
    if file_checks['status'] == 'fail':
        flags.append('file checks failed: ' + '; '.join(file_checks['issues']))
    if content_checks['status'] == 'fail':
        flags.append('required fields could not be extracted: ' + ', '.join(content_checks['missing_fields']))
    if address_document and not corrected:
        flags.append('SIMULATED AI ANALYSIS: business address mismatch detected.')
    if tamper_checks['status'] == 'flag' and (doc_label in ('PAN', 'IDENTITY')):
        flags.append('tamper triage flagged the document: ' + '; '.join(tamper_checks['indicators']))

    if flags:
        confidence = 72
        status = 'RESUBMISSION_REQUIRED'
        issue = '; '.join(flags) + ' Upload a corrected document for revalidation.'
        application.status = 'CORRECTION_REQUIRED'
        application.correction_notes = issue
        db.session.add(ApplicationStatusHistory(
            application_id=application.id, status='CORRECTION_REQUIRED', changed_by_id=user.id, notes=issue
        ))
        db.session.add(Notification(
            user_id=application.applicant_id, title='Document resubmission required',
            message=issue, type='WARNING', related_application_id=application.id
        ))
    else:
        confidence = 96 if address_document else 98
        status = 'UNDER_OFFICER_REVIEW'
        issue = ('SIMULATED AI ANALYSIS: file, content and consistency checks passed. '
                 'Awaiting licence officer verification — official verification is NOT performed '
                 'by the automated system.')
        if application.status in ('CORRECTION_REQUIRED', 'ADDITIONAL_DOCUMENTS_REQUIRED'):
            application.status = 'DOCUMENT_VALIDATION'
            application.correction_notes = None
            db.session.add(ApplicationStatusHistory(
                application_id=application.id, status='DOCUMENT_VALIDATION', changed_by_id=user.id,
                notes='SIMULATED AI revalidation passed after corrected document upload.'
            ))

    doc.verification_status = status
    doc.verification_notes = issue
    doc.ocr_data = json.dumps({
        'simulated_ai': True,
        'confidence': confidence,
        'extracted_fields_masked': _mask_fields(fields),
        'decision_reason': issue,
        'validation_report': {
            'file_checks': file_checks,
            'content_checks': content_checks,
            'tamper_checks': tamper_checks,
            'official_verification': {
                'required': True,
                'performed': False,
                'note': 'Official verification is only performed by the accountable licence officer; '
                        'the automated system never claims government verification.'
            },
            'verdict': status,
        },
    })
    doc.status = doc.verification_status
    db.session.add(AuditLog(
        application_id=application.id, user_id=user.id,
        action='AI_DOCUMENT_PREVALIDATED',
        details=f'SIMULATED AI layered pre-validation: {doc.original_filename} → {status} ({confidence}% confidence).'
    ))
    return {
        'status': status, 'confidence': confidence, 'issue': issue,
        'checks': {
            'file': file_checks, 'content': content_checks, 'tamper': tamper_checks,
            'official_verification': {
                'required': True, 'performed': False,
                'note': 'Official verification is performed by the licence officer, never simulated.'
            },
        },
        'simulated': True,
    }

@documents_bp.route('/repository', methods=['GET'])
@jwt_required()
def document_repository():
    """Shared document repository: ALL users can browse docs in scope.
    ADMIN sees everything; APPLICANT sees their own; INSPECTOR/ADMIN see docs
    linked to inspections they are part of."""
    user = get_current_user()
    docs = Document.query.all()

    if user.role == 'ADMIN' or user.role == 'AI_AGENT':
        scope = docs
    elif user.role == 'APPLICANT':
        scope = [d for d in docs if d.business_id and Business.query.get(d.business_id) and Business.query.get(d.business_id).owner_id == user.id]
    else:  # INSPECTOR / other — docs for any application that has an inspection
        scope = []
        for d in docs:
            app = Application.query.get(d.application_id) if d.application_id else None
            if app and app.inspections:
                scope.append(d)

    return jsonify({'documents': [d.to_dict() for d in scope]}), 200

@documents_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_document():
    user = get_current_user()
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed. Allowed: PDF, PNG, JPG, JPEG, DOC, DOCX'}), 400
    
    application_id = request.form.get('application_id')
    requirement_id = request.form.get('requirement_id')
    doc_type = request.form.get('doc_type', 'OTHER')
    
    if not application_id:
        return jsonify({'error': 'application_id is required'}), 400
    
    application = Application.query.get(application_id)
    if not application:
        return jsonify({'error': 'Application not found'}), 404
    
    if user.role == 'APPLICANT' and application.applicant_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Check file size (max 16MB already set by Flask)
    original_filename = secure_filename(file.filename)
    ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else 'bin'
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    
    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_path = os.path.join(upload_folder, unique_filename)
    file.save(file_path)
    
    file_size = os.path.getsize(file_path)
    
    # Keep existing documents as-is; add new independent record.
    # Multiple documents per requirement are allowed for accountability, and the
    # latest upload for that requirement is the version under review.
    document_version = 1
    if requirement_id:
        prior = Document.query.filter_by(application_id=application_id, requirement_id=requirement_id).all()
        document_version = max([d.document_version or 1 for d in prior], default=0) + 1 if prior else 1

    doc = Document(
        application_id=application_id,
        business_id=application.business_id,
        requirement_id=requirement_id,
        uploader_id=user.id,
        filename=unique_filename,
        original_filename=original_filename,
        doc_type=doc_type,
        file_path=file_path,
        file_size=file_size,
        mime_type=file.content_type or 'application/octet-stream',
        document_version=document_version,
        status='VALIDATION_PENDING',
        verification_status='VALIDATION_PENDING'
    )
    db.session.add(doc)
    db.session.flush()
    
    # Run OCR (mock in demo) and mask sensitive values BEFORE storage.
    ocr_result = process_document_ocr(file_path, doc_type)
    doc.ocr_text = _mask_sensitive(ocr_result.get('text', ''))
    doc.ocr_data = json.dumps(_mask_fields(ocr_result.get('extracted_fields', {})))

    ai_result = run_demo_prevalidation(doc, application, user)
    
    log = AuditLog(
        application_id=application_id,
        user_id=user.id,
        action='DOCUMENT_UPLOADED',
        details=f'Document "{original_filename}" uploaded for {doc_type}'
    )
    db.session.add(log)

    # Automatic AI re-review: as soon as the uploaded set is fully verified,
    # the AI Compliance Agent re-runs its review and advances the workflow
    # (inspection assignment / officer decision gate) without manual re-trigger.
    # The gate is strict: EVERY required document must be individually verified
    # before a single upload advances the application.
    if (application.status in ['SUBMITTED', 'UNDER_REVIEW', 'DOCUMENT_VALIDATION',
                               'CORRECTION_REQUIRED', 'ADDITIONAL_DOCUMENTS_REQUIRED']
            and ai_decision_service.all_mandatory_documents_approved(application)):
        ai_decision_service.review_and_advance(application, user, enrich=False)

    db.session.commit()
    publish([application.applicant_id, application.assigned_officer_id],
            'application_update', {'application_id': application.id,
                                   'application_number': application.application_number,
                                   'status': application.status})
    
    return jsonify({'document': doc.to_dict(), 'ocr_result': {'extracted_fields': _mask_fields(ocr_result.get('extracted_fields', {})), 'confidence': ocr_result.get('confidence')}, 'ai_prevalidation': ai_result}), 201

@documents_bp.route('/application/<app_id>', methods=['GET'])
@jwt_required()
def get_application_documents(app_id):
    user = get_current_user()
    application = Application.query.get_or_404(app_id)
    
    if user.role == 'APPLICANT' and application.applicant_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    docs = Document.query.filter_by(application_id=app_id).all()
    
    # Get requirements
    requirements = DocumentRequirement.query.filter_by(
        approval_type_id=application.approval_type_id
    ).all()
    
    # Per-requirement view built from the ACTUAL document rows: every uploaded
    # document stays an independent record (multiple docs per requirement are
    # allowed), and a requirement with no upload at all reports NOT_UPLOADED so
    # the applicant/officer can see exactly which pieces are still missing.
    docs_by_req = {}
    for d in docs:
        if d.requirement_id:
            docs_by_req.setdefault(d.requirement_id, []).append(d)
    
    req_status = []
    for req in requirements:
        req_docs = docs_by_req.get(req.id, [])
        latest = req_docs[-1] if req_docs else None
        req_status.append({
            'requirement': req.to_dict(),
            'document': latest.to_dict() if latest else None,
            'documents': [d.to_dict() for d in req_docs],
            'uploaded': bool(req_docs),
            # Effective per-requirement status: NOT_UPLOADED when nothing was
            # uploaded yet, otherwise the LAST uploaded document's status.
            'status': latest.verification_status if latest else 'NOT_UPLOADED',
        })
    
    return jsonify({
        'documents': [d.to_dict() for d in docs],
        'requirements': req_status
    }), 200


@documents_bp.route('/reuse', methods=['POST'])
@jwt_required()
def reuse_document():
    """Reuse a previously VERIFIED document of the same business in another
    application of the same approval type (verify once, reuse everywhere)."""
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    application_id = data.get('application_id')
    requirement_id = data.get('requirement_id')
    source_document_id = data.get('source_document_id')

    if not all([application_id, requirement_id, source_document_id]):
        return jsonify({'error': 'application_id, requirement_id and source_document_id are required'}), 400

    application = Application.query.get_or_404(application_id)
    if user.role == 'APPLICANT' and application.applicant_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    source = Document.query.get_or_404(source_document_id)
    if source.business_id != application.business_id:
        return jsonify({'error': 'The source document belongs to a different business and cannot be reused.'}), 400
    if source.verification_status != 'VERIFIED' or source.status != 'VERIFIED':
        return jsonify({'error': 'Only previously verified documents can be reused.'}), 400

    requirement = DocumentRequirement.query.get(requirement_id)
    if not requirement or requirement.approval_type_id != application.approval_type_id:
        return jsonify({'error': 'The document requirement does not belong to this application.'}), 400

    existing = Document.query.filter_by(
        application_id=application_id, requirement_id=requirement_id
    ).first()
    if existing:
        return jsonify({'error': 'This requirement already has a document. Replace or delete it first.'}), 400

    ext = (source.filename or '').rsplit('.', 1)[-1].lower() if '.' in (source.filename or '') else 'bin'
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    upload_folder = current_app.config['UPLOAD_FOLDER']
    file_path = os.path.join(upload_folder, unique_filename)
    if source.file_path and os.path.exists(source.file_path):
        shutil.copyfile(source.file_path, file_path)
        file_size = os.path.getsize(file_path)
    else:
        file_path = None
        file_size = source.file_size

    doc = Document(
        application_id=application_id,
        business_id=application.business_id,
        requirement_id=requirement_id,
        uploader_id=user.id,
        filename=unique_filename,
        original_filename=f"{source.original_filename} (reused)",
        doc_type=requirement.code,
        file_path=file_path,
        file_size=file_size,
        mime_type=source.mime_type,
        status='UPLOADED',
        verification_status='VERIFIED',
        verification_notes=f'Reused from "{source.original_filename}" — previously verified by the simulated AI (verified once, reused across approvals).',
        ocr_text=source.ocr_text,
        ocr_data=source.ocr_data,
        verified_at=now(),
    )
    db.session.add(doc)
    db.session.add(AuditLog(
        application_id=application_id, user_id=user.id,
        action='DOCUMENT_REUSED',
        details=f'Reused verified document "{source.original_filename}" for {requirement.name}.',
    ))
    db.session.add(Notification(
        user_id=application.applicant_id, title='Document reused',
        message=f'A previously verified document was reused for {application.application_number}.',
        type='SUCCESS', related_application_id=application_id,
    ))

    # Automatic AI re-review: reuse may complete the application's verified
    # document set, so advance the workflow through the shared engine.
    if (application.status in ['SUBMITTED', 'UNDER_REVIEW', 'DOCUMENT_VALIDATION',
                               'CORRECTION_REQUIRED', 'ADDITIONAL_DOCUMENTS_REQUIRED']
            and ai_decision_service.document_health(application)['status'] == 'VERIFIED'):
        ai_decision_service.review_and_advance(application, user, enrich=False)

    db.session.commit()
    publish([application.applicant_id, application.assigned_officer_id],
            'application_update', {'application_id': application.id,
                                   'application_number': application.application_number,
                                   'status': application.status})
    return jsonify({'document': doc.to_dict()}), 201


@documents_bp.route('/<doc_id>/preview', methods=['GET'])
@jwt_required()
def preview_document(doc_id):
    """Return a safe preview location and AI result for the document viewer."""
    user = get_current_user()
    doc = Document.query.get_or_404(doc_id)
    application = Application.query.get(doc.application_id)
    if user.role == 'APPLICANT' and application.applicant_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    return jsonify({
        'document': doc.to_dict(),
        'preview_url': f'/uploads/{doc.filename}' if doc.filename else None,
        'notice': 'DEMO DOCUMENT PREVIEW — simulated data; not a government record.'
    }), 200

@documents_bp.route('/<doc_id>/verify', methods=['POST'])
@jwt_required()
def verify_document(doc_id):
    user = get_current_user()
    if user.role not in ['AI_AGENT', 'ADMIN', 'OFFICER']:
        return jsonify({'error': 'AI Agent, Admin, or Officer access required'}), 403
    
    doc = Document.query.get_or_404(doc_id)
    data = request.get_json()
    
    doc.verification_status = data.get('status', 'APPROVED')
    doc.verification_notes = data.get('notes', '')
    doc.verified_by_id = user.id
    doc.verified_at = now()
    # A rejected document carries its definitive reason; approving one clears a
    # previous rejection reason so stale reasons never linger on a valid doc.
    doc.rejection_reason = None
    
    if doc.verification_status in ('APPROVED', 'VERIFIED'):
        doc.status = 'APPROVED' if doc.verification_status == 'APPROVED' else 'VERIFIED'
    elif doc.verification_status == 'REJECTED':
        doc.status = 'REJECTED'
        doc.rejection_reason = data.get('rejection_reason', data.get('reason', 'Document rejected by officer.'))
    elif doc.verification_status == 'RESUBMISSION_REQUIRED':
        doc.status = 'RESUBMISSION_REQUIRED'
        doc.rejection_reason = data.get('rejection_reason', data.get('reason', 'Officer requested a corrected document.'))
    elif doc.verification_status in ('UNDER_REVIEW', 'UNDER_OFFICER_REVIEW'):
        doc.status = doc.verification_status
    
    log = AuditLog(
        application_id=doc.application_id,
        user_id=user.id,
        action='DOCUMENT_VERIFIED',
        details=f'Document "{doc.original_filename}" marked as {doc.verification_status}' + (f' | Reason: {doc.rejection_reason}' if doc.rejection_reason else '')
    )
    db.session.add(log)
    db.session.commit()

    # After the officer individually approves/rejects a document, push the
    # per-document outcome to the applicant (and the officer's own desk) in
    # real time — the applicant sees the exact rejection reason immediately,
    # even when the other documents are still pending.
    application = Application.query.get(doc.application_id)
    publish([application.applicant_id if application else None,
             application.assigned_officer_id if application else None],
            'document_update',
            {'application_id': doc.application_id,
             'application_number': application.application_number if application else None,
             'document_id': doc.id,
             'document_type': doc.doc_type,
             'requirement_id': doc.requirement_id,
             'verification_status': doc.verification_status,
             'rejection_reason': doc.rejection_reason,
             'application_status': application.status if application else None})

    # After the officer individually verifies/rejects a document, check if
    # ALL mandatory documents have now been individually reviewed.
    # If so, advance the application through the shared engine.
    if application and ai_decision_service.all_mandatory_documents_approved(application):
        ai_decision_service.review_and_advance(application, user, enrich=False)
        db.session.commit()
        publish([application.applicant_id, application.assigned_officer_id],
                'application_update', {'application_id': application.id,
                                       'application_number': application.application_number,
                                       'status': application.status})

    return jsonify({'document': doc.to_dict()}), 200

@documents_bp.route('/<doc_id>', methods=['DELETE'])
@jwt_required()
def delete_document(doc_id):
    user = get_current_user()
    doc = Document.query.get_or_404(doc_id)
    
    application = Application.query.get(doc.application_id)
    if user.role == 'APPLICANT' and application.applicant_id != user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if application.status not in ['DRAFT', 'CORRECTION_REQUIRED']:
        return jsonify({'error': 'Cannot delete document in current application status'}), 400
    
    try:
        if doc.file_path and os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except:
        pass
    
    db.session.delete(doc)
    db.session.commit()
    return jsonify({'message': 'Document deleted'}), 200

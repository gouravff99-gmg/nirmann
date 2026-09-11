from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .. import db
from ..models import User, Business, Application, Notification, ApprovalType

assistant_bp = Blueprint('assistant', __name__)

def get_current_user():
    """Delegate to the shared 401-safe helper (no silent None)."""
    from .utils import get_current_user as _shared
    return _shared()

RESPONSES = {
    'what approvals': 'Based on your business profile, I can see the customized approval checklist on your business dashboard. Key approvals depend on your sector, operations, and location. Click on any business to view its specific checklist.',
    'fire': 'The Fire Safety NOC is required for businesses with physical infrastructure. It involves an inspection by the Fire Department and typically takes 10 days. Required documents: Fire safety plan, building layout, fire extinguisher records.',
    'food': 'Food-related businesses need: FSSAI Food License, Trade License, and potentially a Health NOC. For food processing units, a Factory License may also be required.',
    'documents': 'Each approval requires specific documents. Visit the Documents section of your application to see exactly what is needed and upload them.',
    'pending': 'Check your Dashboard for all pending applications. Applications in "SUBMITTED", "UNDER REVIEW", "DOCUMENT VALIDATION" or "CORRECTION REQUIRED" status are being processed by the AI Compliance Agent.',
    'inspection': 'Inspections are physical visits by authorized inspectors. You will be notified when one is scheduled. The inspector will verify compliance with safety and operational requirements.',
    'certificate': 'Certificates are issued after approval. They are PROTOTYPE certificates for this SIH demonstration. Each has a unique verification ID and validity period.',
    'renewal': 'Certificates need renewal before expiry. You will receive reminders at 60, 30, and 7 days before expiry. Visit the Certificates section to renew.',
    'grievance': 'You can raise a grievance from the Grievances section if you face issues with your application process. Provide details about your concern and it will be reviewed.',
    'status': 'Application statuses: DRAFT → SUBMITTED → UNDER_REVIEW → CORRECTION_REQUIRED / INSPECTION_REQUIRED → APPROVED / REJECTED.',
    'how long': 'Processing times vary by approval type. Each approval shows estimated processing time. SLA deadlines are tracked and visible to applicants and admins.',
    'hello': 'Hello! I am the NIRMAN Assistant. I can help you understand approvals, documents, application status, and next steps. What would you like to know?',
    'hi': 'Hi! How can I help you today with your business approvals?',
    'help': 'I can help with: approval requirements, required documents, application status, inspection process, certificates, and renewal. Just ask your question!',
}

@assistant_bp.route('/chat', methods=['POST'])
@jwt_required()
def chat():
    user = get_current_user()
    data = request.get_json()
    message = data.get('message', '').lower().strip()
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    
    # Get user context
    businesses = Business.query.filter_by(owner_id=user.id).all() if user.role == 'APPLICANT' else []
    apps = Application.query.filter_by(applicant_id=user.id).all() if user.role == 'APPLICANT' else []
    
    # Find response
    response_text = None
    for keyword, response in RESPONSES.items():
        if keyword in message:
            response_text = response
            break
    
    if not response_text:
        # Context-aware response
        if 'my business' in message or 'businesses' in message:
            if businesses:
                names = ', '.join(b.name for b in businesses)
                response_text = f'You have {len(businesses)} business(es): {names}. Click on any to view its approval checklist and status.'
            else:
                response_text = 'You have not created any businesses yet. Click "Register Business" to get started.'
        
        elif 'application' in message:
            if apps:
                pending = [a for a in apps if a.status not in ['APPROVED', 'REJECTED']]
                response_text = f'You have {len(apps)} application(s), {len(pending)} pending. Visit your dashboard for details.'
            else:
                response_text = 'You have no applications yet. Start by registering a business and generating your approval checklist.'
        
        elif any(w in message for w in ['msme', 'scheme', 'incentive', 'subsidy', 'grant']):
            response_text = 'Visit the Schemes & Incentives section to see DEMO scheme recommendations based on your business profile. These are illustrative examples only and not verified government advice.'
        
        elif any(w in message for w in ['ai', 'agent', 'review', 'reviewed']):
            response_text = 'Once you submit an application, the AI Compliance Agent pre-validates documents, checks configured rules and your risk profile, then processes routine checks. It may request corrections, schedule an inspection, or prepare an approval-ready decision that an accountable Admin reviews.'
        
        else:
            response_text = f'I understand you are asking about "{message}". For specific guidance, please visit the relevant section of NIRMAN. I can help with: approvals, documents, status, inspections, certificates, renewal, and schemes. ⚠️ Note: This is a prototype system. Always verify requirements with actual government departments.'
    
    # Add user-specific context
    if businesses and 'next' in message:
        pending_apps = [a for a in apps if a.status in ['DRAFT', 'CORRECTION_REQUIRED']]
        if pending_apps:
            response_text += f' Your immediate next step: {pending_apps[0].application_number} needs attention (status: {pending_apps[0].status}).'
    
    return jsonify({
        'response': response_text,
        'disclaimer': 'This is an AI assistant for the NIRMAN SIH prototype. Responses are illustrative and should not be treated as official government advice.'
    }), 200

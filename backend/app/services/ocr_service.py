"""
NIRMAN Mock OCR Service
=======================
This is a clearly separated MOCK OCR service for SIH prototype.
In production, replace with Tesseract, Google Vision, or government-approved OCR.

The service simulates document text extraction and field extraction.
"""
import os
import re


def process_document_ocr(file_path, doc_type='OTHER'):
    """
    Process a document with OCR.
    
    Returns:
        dict with 'text', 'extracted_fields', 'confidence', 'is_mock'
    
    Note: This is a MOCK OCR service for demonstration.
    Real OCR would use Tesseract or cloud vision APIs.
    """
    result = {
        'text': '',
        'extracted_fields': {},
        'confidence': 0.0,
        'is_mock': True,
        'note': 'DEMO: This is a simulated OCR extraction for the SIH prototype.'
    }
    
    # Try real Tesseract if available
    try:
        import pytesseract
        from PIL import Image
        
        ext = file_path.rsplit('.', 1)[-1].lower() if '.' in file_path else ''
        if ext in ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff']:
            img = Image.open(file_path)
            ocr_text = pytesseract.image_to_string(img)
            if ocr_text.strip():
                result['text'] = ocr_text
                result['confidence'] = 0.85
                result['is_mock'] = False
                result['extracted_fields'] = extract_fields_from_text(ocr_text, doc_type)
                return result
    except Exception:
        pass  # Fall through to mock
    
    # Mock OCR based on document type
    result['text'], result['extracted_fields'], result['confidence'] = get_mock_ocr(doc_type)
    return result


def extract_fields_from_text(text, doc_type):
    """Extract key fields from OCR text using regex patterns."""
    fields = {}
    
    # PAN Card
    pan_match = re.search(r'[A-Z]{5}[0-9]{4}[A-Z]', text)
    if pan_match:
        fields['pan_number'] = pan_match.group()
    
    # Name patterns
    name_match = re.search(r'Name[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)', text)
    if name_match:
        fields['name'] = name_match.group(1)
    
    # Date patterns
    date_match = re.search(r'\d{2}/\d{2}/\d{4}', text)
    if date_match:
        fields['date'] = date_match.group()
    
    # Aadhar
    aadhar_match = re.search(r'\d{4}\s\d{4}\s\d{4}', text)
    if aadhar_match:
        fields['aadhar_number'] = aadhar_match.group()
    
    return fields


def get_mock_ocr(doc_type):
    """Return mock OCR data for demonstration."""
    mock_data = {
        'PAN': (
            'FORM 60\nPERMANENT ACCOUNT NUMBER CARD\nIncome Tax Department\nGovt. of India\nName: GOURAV KUMAR\nFather\'s Name: RAJESH KUMAR\nDate of Birth: 15/03/1990\nPAN: ABCPG1234G\nSignature',
            {'name': 'GOURAV KUMAR', 'pan_number': 'ABCPG1234G', 'dob': '15/03/1990'},
            0.92
        ),
        'IDENTITY': (
            'GOVERNMENT OF INDIA\nADHAAR CARD\nName: Gourav Kumar\nDOB: 15/03/1990\nGender: MALE\nAddress: 123 MG Road, Bengaluru, Karnataka - 560001\nAadhar: 1234 5678 9012',
            {'name': 'Gourav Kumar', 'aadhar_number': '1234 5678 9012', 'gender': 'MALE'},
            0.90
        ),
        'BUSINESS_REGISTRATION': (
            'MINISTRY OF CORPORATE AFFAIRS\nCERTIFICATE OF INCORPORATION\nThis is to certify that\nFRESHBITE FOODS PRIVATE LIMITED\nCIN: U15200KA2026PTC001234\nDate of Incorporation: 15/01/2026\nRegistered Office: Bengaluru, Karnataka',
            {'company_name': 'FRESHBITE FOODS PRIVATE LIMITED', 'cin': 'U15200KA2026PTC001234', 'incorporation_date': '15/01/2026'},
            0.88
        ),
        'FIRE_SAFETY': (
            'FIRE SAFETY COMPLIANCE REPORT\nPremises: 123 Industrial Area, Bengaluru\nType: Food Processing Unit\nFire Extinguishers: 8 units (ABC type)\nEmergency Exits: 4 marked exits\nElectrical Safety: Certified\nDate: 01/06/2026\nInspected By: Fire Safety Engineer',
            {'premises': '123 Industrial Area, Bengaluru', 'extinguishers': '8', 'exits': '4'},
            0.87
        ),
        'LAYOUT_PLAN': (
            'APPROVED BUILDING LAYOUT PLAN\nPlot No: 456\nArea: 2500 sq.m.\nBuilding Type: Industrial\nFloors: Ground + 1st\nApproved By: Planning Authority\nApproval No: BLD-2026-1234\nDate: 15/02/2026',
            {'plot_number': '456', 'area': '2500 sq.m.', 'approval_number': 'BLD-2026-1234'},
            0.85
        ),
    }
    
    default = (
        f'DOCUMENT TYPE: {doc_type}\n[Mock OCR extraction for SIH prototype]\nDocument appears to be valid.\nAll fields extracted successfully.',
        {'doc_type': doc_type, 'status': 'EXTRACTED'},
        0.80
    )
    
    text, fields, confidence = mock_data.get(doc_type, default)
    return text, fields, confidence

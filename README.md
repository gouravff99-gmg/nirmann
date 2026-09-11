# NIRMAN — One Platform for Smarter Business Approvals
## Smart India Hackathon 2026 — Prototype

> ⚠️ **PROTOTYPE / DEMO** — All data, certificates, and approvals in this application are for demonstration purposes only. This is NOT connected to any real government system.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- pip3

### One-Command Start
```bash
cd /Users/gmgourav/Desktop/NIRMAN
./start.sh
```

Then open **http://localhost:5001** in your browser.

### Manual Start
```bash
cd backend
pip3 install -r requirements.txt
python3 seed.py       # First time only — seeds demo data
python3 run.py
```

---

## 📋 Demo Credentials

| Role | Email | Password |
|------|-------|----------|
| 👤 Applicant | applicant@demo.com | Demo@1234 |
| 🔍 Inspector | inspector@demo.com | Demo@1234 |
| ⚙️ Admin | admin@demo.com | Demo@1234 |
| 🤖 AI Compliance Agent | System role — enter via the "AI DEMO" button in the app | — |

---

## 🏗️ Architecture

```
nirman/
├── backend/
│   ├── app/
│   │   ├── __init__.py          # Flask app factory
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   ├── routes/
│   │   │   ├── auth.py          # Authentication (JWT)
│   │   │   ├── businesses.py    # Business management
│   │   │   ├── applications.py  # Application lifecycle
│   │   │   ├── documents.py     # Document upload + OCR
│   │   │   ├── ai_agent.py      # AI Compliance Agent (review + decision)
│   │   │   ├── inspector.py     # Inspection management
│   │   │   ├── certificates.py  # Certificate + renewal
│   │   │   ├── admin.py         # Admin + analytics
│   │   │   ├── notifications.py # Notification center
│   │   │   ├── grievances.py    # Grievance management
│   │   │   ├── approvals.py     # Approval types + schemes
│   │   │   └── assistant.py     # NIRMAN AI assistant
│   │   └── services/
│   │       ├── ai_decision_service.py # Deterministic AI decision engine
│   │       ├── ai_service.py          # Ollama LLM enrichment + fallback
│   │       ├── approval_engine.py     # Dynamic rule engine
│   │       └── ocr_service.py         # Mock OCR service
│   ├── seed.py                  # Demo data seeder
│   ├── run.py                   # Entry point
│   ├── requirements.txt
│   └── nirman.db                # SQLite database
├── frontend/
│   ├── index.html               # Vanilla SPA (inline script + AI extension)
│   └── js/ai-upgrade.js         # AI Compliance Agent UI
└── start.sh                     # One-click startup script
```

---

## ✨ Key Features

### 🏢 Business Onboarding
- **Multi-step wizard** — Business registration with 4-step form
- **Dynamic approval checklist** — Rule-based engine generates customized approval lists based on sector, operations, employee count, infrastructure, and more
- **Smart classification** — Automatic MSME size classification (Small/Medium/Large)

### 📋 Dynamic Approval Engine
The core innovation — evaluates business attributes against configurable rules:
- Food businesses → FSSAI licence + Health NOC
- Manufacturing → Factory licence + Pollution control + Electrical safety
- 10+ employees → Labour registration required
- Hazardous materials → Hazardous material licence
- Physical premises → Fire NOC + Trade licence

### 📄 Document Management
- **Upload** — Multi-format support (PDF, PNG, JPG, DOC)
- **Mock OCR** — Simulates text extraction and field parsing
- **Requirement tracking** — Visual status for each required document
- **AI document verification** — AI pre-validation with confidence score, re-validation on corrected uploads

### 🔄 Application Workflow
Full state machine: `DRAFT → SUBMITTED → UNDER_REVIEW → CORRECTION_REQUIRED / INSPECTION_REQUIRED → APPROVED / REJECTED`

### 🤖 AI Compliance Agent
The application's review step is handled entirely by an autonomous AI Compliance Agent:
- **Deterministic decision engine** — evaluates mandatory checklist coverage, document health, inspection results and a modelled business risk score (LOW/MEDIUM/HIGH)
- **Transparent decisions** — every review shows its reasoning: evaluated checklist items, document/inspection checks, risk factors and confidence
- **Local LLM enrichment** — explanations are enriched by an Ollama model (qwen2.5-coder) when available; the rule engine always remains as a fallback
- **Decision queue** — live queue of applications ready for AI review with one-click "Run review"
- **Audit trail** — every AI review is persisted to the audit log; humans (Admin) can override any AI decision, which is also audit-logged

### 🔍 Inspection Management
- AI Compliance Agent triggers inspections based on risk (high/medium-risk applications)
- Inspector schedules date
- Inspector submits digital checklist with remarks
- Evidence upload support
- Recommendation: APPROVE / CORRECTION / REJECT — fed back into the AI decision engine

### 🏅 Certificates (Prototype)
- Auto-generated upon approval
- Unique certificate number + verification ID
- QR code data for verification
- Renewal tracking with 60/30/7-day reminders

### 📊 Admin Analytics
- Application volume by status and department
- SLA monitoring with breach detection
- Department performance table
- Monthly trend charts
- Full audit trail

### 🤖 NIRMAN Assistant
Context-aware chatbot for applicants with keyword-based responses about the approval process.

### 🔔 Notifications
Real-time notifications for every status change, correction request, inspection scheduling, and certificate issuance.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 (CDN) + Tailwind CSS + Recharts |
| Backend | Python 3.13 + Flask 3.1 |
| Auth | JWT (flask-jwt-extended) + bcrypt |
| Database | SQLite (via SQLAlchemy) |
| OCR | Mock OCR + pytesseract (if available) |
| Charts | Recharts |

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/register` | Register |
| GET | `/api/businesses/` | List businesses |
| POST | `/api/businesses/` | Create business |
| GET | `/api/businesses/:id/checklist` | Get approval checklist |
| GET | `/api/applications/` | List applications |
| POST | `/api/applications/` | Create application |
| POST | `/api/applications/:id/submit` | Submit application |
| POST | `/api/documents/upload` | Upload document |
| GET | `/api/ai-agent/dashboard` | AI Compliance Agent dashboard |
| GET | `/api/ai-agent/queue` | AI decision queue |
| GET | `/api/ai-agent/application/:id/decision` | Compute + read AI decision for an application |
| POST | `/api/ai-agent/application/:id/review` | Persist AI review + transition status |
| GET | `/api/inspector/dashboard` | Inspector dashboard |
| POST | `/api/inspector/:id/submit-report` | Submit inspection report |
| GET | `/api/admin/dashboard` | Admin dashboard |
| GET | `/api/admin/analytics` | Analytics data |
| GET | `/api/certificates/my-certificates` | List certificates |
| GET | `/api/certificates/verify/:verification_id` | Verify certificate |
| GET | `/api/notifications/` | List notifications |
| POST | `/api/grievances/` | File grievance |
| GET | `/api/approvals/schemes` | List schemes |
| POST | `/api/assistant/chat` | Chat with NIRMAN assistant |

---

## ⚠️ Important Disclaimers

1. **Prototype Only** — This is an SIH competition prototype, NOT a production system
2. **Demo Data** — All businesses, applications, approvals, and certificates are fictional
3. **No Real Integration** — Not connected to any government APIs (MCA21, FSSAI portal, etc.)
4. **Mock OCR** — OCR extraction is simulated, not real document verification
5. **Prototype Certificates** — All certificates clearly marked as PROTOTYPE
6. **No Legal Advice** — The approval requirements shown are illustrative only
7. **Approval Rules** — The rule-based engine is a demonstration of the concept, not verified legal requirements
8. **AI Decisions** — AI determinations are computed by a deterministic demo rule engine (optionally enriched by a local LLM); they are illustrative, never real regulatory decisions.

---

## 🇮🇳 SIH 2026 Context

NIRMAN addresses the problem of fragmented business approval processes across multiple government departments. The platform demonstrates:
- **Single window** for discovering all required approvals
- **Transparency** through real-time status tracking
- **Accountability** through audit trails and SLA monitoring
- **Efficiency** through dynamic checklist generation and digital workflows
- **Traceability** through complete application history

---

*Built for Smart India Hackathon 2026 — Prototype demonstration only*

from app import create_app, db
import os, time

app = create_app()

# Serve frontend static files
from flask import send_from_directory, make_response

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')

@app.route('/')
def index():
    resp = make_response(send_from_directory(FRONTEND_DIR, 'index.html'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    # Let the file mtime drive revalidation so aggressive caches are always
    # bypassed after we edit index.html (the old pre-fix file may have been
    # cached without these headers).
    resp.headers['Last-Modified'] = time.strftime(
        '%a, %d %b %Y %H:%M:%S GMT', time.gmtime(os.path.getmtime(
            os.path.join(FRONTEND_DIR, 'index.html'))))
    return resp

@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'css'), filename)

@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'js'), filename)

# Legacy routes kept for compatibility
@app.route('/static/js/<path:filename>')
def serve_static_js(filename):
    return send_from_directory(FRONTEND_DIR, filename)

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# SPA catch-all: any non-API, non-static URL serves index.html so that
# refreshing (or deep-linking to) any client-side route never 404s.
from flask import request, jsonify

@app.errorhandler(404)
def spa_fallback(e):
    path = request.path
    if path.startswith('/api/') or path.startswith('/css/') or \
       path.startswith('/js/') or path.startswith('/uploads/') or \
       path.startswith('/static/'):
        return jsonify({'error': 'Not found', 'msg': 'The requested URL was not found on the server.'}), 404
    return send_from_directory(FRONTEND_DIR, 'index.html')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # ── Schema migration: add licence-knowledge columns if missing ───
        try:
            import sqlite3, json
            db_path = app.config.get('SQLALCHEMY_DATABASE_URI','').replace('sqlite:///','')
            conn = sqlite3.connect(db_path)
            cur = conn.execute("PRAGMA table_info(approval_types)")
            existing_cols = {row[1] for row in cur.fetchall()}
            if 'official_sources' not in existing_cols:
                conn.execute("ALTER TABLE approval_types ADD COLUMN official_sources TEXT DEFAULT '[]'")
                print("   🔧 Added approval_types.official_sources column")
            if 'reference_url' not in existing_cols:
                conn.execute("ALTER TABLE approval_types ADD COLUMN reference_url TEXT")
                print("   🔧 Added approval_types.reference_url column")
            conn.commit()
            # Populate licence knowledge data — ONLY the 6 licences shown in the
            # Licence & Knowledge Center, each with its official government URL.
            # These exactly match backend/seed.py so a startup cannot ever
            # overwrite the seed's official sources with placeholder links.
            LICENCE_KNOWLEDGE = {
                'FSSAI': {
                    'official_sources': [
                        {'name': 'FSSAI Food License', 'url': 'https://foscos.fssai.gov.in/'},
                    ],
                    'reference_url': 'https://foscos.fssai.gov.in/'
                },
                'FIRE_NOC': {
                    'official_sources': [
                        {'name': 'Fire Safety NOC', 'url': 'https://services.india.gov.in/'},
                    ],
                    'reference_url': 'https://services.india.gov.in/'
                },
                'GST_REG': {
                    'official_sources': [
                        {'name': 'GST Registration', 'url': 'https://services.india.gov.in/service/detail/gst-registration-1'},
                    ],
                    'reference_url': 'https://services.india.gov.in/service/detail/gst-registration-1'
                },
                'LABOUR_REG': {
                    'official_sources': [
                        {'name': 'Labour Registration', 'url': 'https://registration.shramsuvidha.gov.in/'},
                    ],
                    'reference_url': 'https://registration.shramsuvidha.gov.in/'
                },
                'POLLUTION_CTO': {
                    'official_sources': [
                        {'name': 'Pollution Control Consent', 'url': 'https://ocmms.nic.in/OCMMS_NEW/'},
                    ],
                    'reference_url': 'https://ocmms.nic.in/OCMMS_NEW/'
                },
                'ELEC_SAFETY': {
                    'official_sources': [
                        {'name': 'Electrical Safety Certificate', 'url': 'https://cea.nic.in/chief-electrical-inspectorate-division/?lang=en'},
                    ],
                    'reference_url': 'https://cea.nic.in/chief-electrical-inspectorate-division/?lang=en'
                },
            }
            for code, knowledge in LICENCE_KNOWLEDGE.items():
                conn.execute(
                    "UPDATE approval_types SET official_sources=?, reference_url=? WHERE code=?",
                    (json.dumps(knowledge['official_sources']), knowledge['reference_url'], code)
                )
            # Only the 6 licences above carry official sources; blank every other
            # licence type so the knowledge centre shows exactly 6 items.
            conn.execute(
                "UPDATE approval_types SET official_sources='[]', reference_url=NULL "
                "WHERE code NOT IN "
                "('FSSAI','FIRE_NOC','GST_REG','LABOUR_REG','POLLUTION_CTO','ELEC_SAFETY')"
            )
            conn.commit()

            # ── Schema migration: add per-document accountability columns ───
            # The Document model tracks verified_by_id + rejection_reason (who
            # reviewed each document and, on rejection, the exact reason). SQLite
            # cannot add columns via db.create_all() on an existing table, so add
            # them on startup exactly like the approval_types columns above.
            cur = conn.execute("PRAGMA table_info(documents)")
            doc_cols = {row[1] for row in cur.fetchall()}
            if 'verified_by_id' not in doc_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN verified_by_id VARCHAR(36)")
                print("   🔧 Added documents.verified_by_id column")
            if 'rejection_reason' not in doc_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN rejection_reason TEXT")
                print("   🔧 Added documents.rejection_reason column")
            if 'document_version' not in doc_cols:
                conn.execute("ALTER TABLE documents ADD COLUMN document_version INTEGER DEFAULT 1")
                print("   🔧 Added documents.document_version column")
            conn.commit()
            conn.close()
            print("   📚 Licence knowledge (official sources) populated")
        except Exception as e:
            print(f"   ⚠️  Licence knowledge migration skipped: {e}")

        # Sector reference + persisted sector→licence assignments. New tables are
        # created by db.create_all(); existing businesses are backfilled here so
        # the DB is the single source of truth for which licences apply.
        try:
            from app.models import Sector, Business, BusinessLicenceAssignment
            for _code in ['FOOD_PROCESSING', 'FOOD_SERVICE', 'RESTAURANT', 'MANUFACTURING',
                          'ELECTRONICS', 'CONSTRUCTION', 'REAL_ESTATE', 'RETAIL', 'WHOLESALE',
                          'SERVICE', 'HEALTHCARE', 'EDUCATION', 'OTHER']:
                if not Sector.query.filter_by(code=_code).first():
                    db.session.add(Sector(code=_code, label=_code.replace('_', ' ').title()))
            db.session.commit()
            from app.services.approval_engine import assign_licences_for_business
            backfilled = 0
            for b in Business.query.all():
                if not BusinessLicenceAssignment.query.filter_by(business_id=b.id).first():
                    assign_licences_for_business(b)
                    backfilled += 1
            if backfilled:
                db.session.commit()
                print(f"   🧩 Persisted licence assignments backfilled for {backfilled} business(es)")
        except Exception:
            import traceback
            traceback.print_exc()

        # Idempotent demo seeding for the Licence Officer / Inspector action
        # demo + deterministic officer assignments. The full pipeline is safe to
        # run on every start so the officer inbox is always consistent from the
        # (single) officer's dominated demo applications, regardless of the
        # current database state.
        try:
            from app.services.officer_seed import ensure_officers, ensure_officer_assignments
            from app.services.demo_officer_seed import ensure_officer_demo_applications

            ensure_officers()
            seeded = ensure_officer_demo_applications()
            if seeded:
                print(f"   🧪 Officer demo applications seeded: {len(seeded)}")
            # Closes any active assignments on the separate parallel-processing
            # demo workbooks and ensures each lifecycle demo app is assigned.
            ensure_officer_assignments()
        except Exception:
            import traceback
            traceback.print_exc()

    port = int(os.environ.get('PORT', 5001))
    print(f"\n🚀 NIRMAN is running at: http://localhost:{port}")
    print(f"📡 API available at:    http://localhost:{port}/api/")
    print(f"\n📋 DEMO CREDENTIALS:")
    print(f"   Applicant: applicant@demo.com / Demo@1234")
    print(f"   Inspector: inspector@demo.com  / Demo@1234")
    print(f"   Admin:     admin@demo.com      / Demo@1234")
    print(f"   🤖 AI Agent: system role — enter via the 'AI DEMO' button in the app\n")
    # Run WITHOUT the auto-reloader: `debug=True` + the default reloader spawns a
    # watchdog child process that is unstable when launched as a background
    # process (leaked semaphores / intermittent crash) and made the app appear
    # to "die", so the login page loaded but API calls failed. Disabling the
    # reloader keeps the server as one stable process.
    app.run(debug=True, use_reloader=False, port=port, host='0.0.0.0')

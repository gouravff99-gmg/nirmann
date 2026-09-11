"""Additive build migration for the Licence Approving Officer feature.

Safety rails:
  * ``db.create_all()`` only creates the NEW tables (officers,
    officer_licences, application_assignments); every existing table is
    untouched, so no data is ever dropped.
  * Officer seeding is idempotent (see app.services.officer_seed).
  * Existing submitted applications that still lack an officer are routed
    deterministically to fill the officer inbox — never overriding an existing
    ACTIVE assignment.

Run from backend/:  python apply_build_migrations.py
"""
from app import create_app, db
from app.services.officer_seed import ensure_officers, ensure_officer_assignments, DEMO_LABEL
from app.models import Officer, User


def main():
    app = create_app()
    with app.app_context():
        db.create_all()
        print('Tables: create_all() complete (new officer tables added, existing tables untouched).')

        created = ensure_officers()
        print(f'Officers: seeded/verified 6 demo officers (created {created} new profiles).')

        assigned = ensure_officer_assignments()
        print(f'Routing: assigned {assigned} existing application(s) to their accountable officer.')

        print('\nOfficer accounts:')
        for profile in Officer.query.order_by(Officer.officer_number).all():
            user = db.session.get(User, profile.user_id)
            codes = ', '.join(ol.approval_type.code for ol in profile.licence_types if ol.approval_type)
            print(f'  {user.email:<32} {user.name:<18} {profile.designation:<28} Licences: {codes}')
        print(f'  {DEMO_LABEL}')

    print('\nBuild migration complete — existing demo data preserved.')


if __name__ == '__main__':
    main()
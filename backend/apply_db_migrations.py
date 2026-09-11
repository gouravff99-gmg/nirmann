"""
Additive DB migration for the account-verification (OTP) feature.

SQLite cannot ALTER-added UNIQUE/CHECK constraints, and ``db.create_all()`` does
not add columns to an existing table — so this script:

  1. Adds the new ``users`` columns if they are missing (simple ALTER TABLE).
  2. Adds a unique index on ``users.phone`` if missing (prevents duplicate
     mobile registration).
  3. Marks the pre-seeded demo accounts (and the AI system role) as VERIFIED so
     they can log in immediately, exactly as required.

It never drops tables or rows, so existing businesses, applications,
inspections, certificates and approvals are preserved. Safe to re-run.
"""
from app import create_app, db
from sqlalchemy import text, bindparam

DEMO_VERIFIED_EMAILS = [
    'applicant@demo.com',
    'applicant2@demo.com',
    'inspector@demo.com',
    'admin@demo.com',
    'ai-agent@system.demo',
]

ADD_COLUMNS = {
    'email_verified': "ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT 0",
    'mobile_verified': "ALTER TABLE users ADD COLUMN mobile_verified BOOLEAN NOT NULL DEFAULT 0",
    'verification_status': "ALTER TABLE users ADD COLUMN verification_status VARCHAR(20) NOT NULL DEFAULT 'UNVERIFIED'",
    'otp_hash': "ALTER TABLE users ADD COLUMN otp_hash VARCHAR(128)",
    'otp_expires_at': "ALTER TABLE users ADD COLUMN otp_expires_at DATETIME",
    'otp_attempts': "ALTER TABLE users ADD COLUMN otp_attempts INTEGER NOT NULL DEFAULT 0",
    'otp_resends': "ALTER TABLE users ADD COLUMN otp_resends INTEGER NOT NULL DEFAULT 0",
    'otp_last_sent_at': "ALTER TABLE users ADD COLUMN otp_last_sent_at DATETIME",
}


def main():
    app = create_app()
    with app.app_context():
        engine = db.engine
        with engine.connect() as conn:
            existing = {row[1] for row in conn.execute(text("PRAGMA table_info(users)"))}

            for col, statement in ADD_COLUMNS.items():
                if col in existing:
                    print(f'  users.{col}: already present — skipped')
                else:
                    conn.execute(text(statement))
                    print(f'  users.{col}: ADDED')

            if 'phone' in existing:
                index_rows = conn.execute(text("PRAGMA index_list(users)")).fetchall()
                index_names = {r[1] for r in index_rows}
                index_exists = any('phone' in name for name in index_names)
                if index_exists:
                    print('  unique index on users.phone: already present — skipped')
                else:
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_phone ON users(phone)"))
                    print('  unique index on users.phone: CREATED')

            # Mark existing demo/system accounts as verified.
            result = conn.execute(text(
                "UPDATE users SET email_verified = 1, mobile_verified = 1, "
                "verification_status = 'VERIFIED' WHERE email IN :emails"
            ).bindparams(bindparam('emails', value=tuple(DEMO_VERIFIED_EMAILS), expanding=True)))
            print(f'  verified demo accounts: {result.rowcount or 0} updated')
            conn.commit()

            # Report final user state (no plain-text secrets included).
            rows = conn.execute(text(
                "SELECT email, role, verification_status, email_verified, mobile_verified, "
                "(CASE WHEN otp_hash IS NULL THEN 0 ELSE 1 END) AS has_otp_digest FROM users ORDER BY email"
            )).fetchall()
            print('\n  users table now:')
            for row in rows:
                print(f'    {row[0]:<26} {row[1]:<10} status={row[2]:<10} '
                      f'email_ok={row[3]} mobile_ok={row[4]} otp_digest_present={row[5]}')

    print('\nMigration complete — demo data preserved.')


if __name__ == '__main__':
    main()
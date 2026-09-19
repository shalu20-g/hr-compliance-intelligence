"""Create (or promote) the first HR_ADMIN account.

Usage:
    python scripts/create_admin.py --name "HR Admin" --email hr@company.com

You will be prompted for a password (never echoed, never stored in plain
text — only a bcrypt hash is saved). If the email already exists, that
account is promoted to HR_ADMIN instead.

This script requires server/terminal access, which is exactly why normal
public registration (``POST /auth/register``) can only ever create EMPLOYEE
accounts — HR_ADMIN cannot be self-granted through the API.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.auth import hash_password
from app.database import get_session_factory, init_db
from app.models.user import EMPLOYEE_ROLE, HR_ADMIN_ROLE, UserRecord, normalize_email


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the first HR_ADMIN account.")
    parser.add_argument("--name", required=True, help="Display name for the admin")
    parser.add_argument("--email", required=True, help="Login email for the admin")
    args = parser.parse_args()

    email = normalize_email(args.email)
    if "@" not in email:
        print("error: --email must be a valid email address", file=sys.stderr)
        return 2
    password = getpass.getpass("Password (min 8 chars): ")
    if len(password) < 8:
        print("error: password must be at least 8 characters", file=sys.stderr)
        return 2

    init_db()
    factory = get_session_factory()
    session = factory()
    try:
        record = session.execute(
            select(UserRecord).where(UserRecord.email == email)
        ).scalar_one_or_none()
        if record is None:
            record = UserRecord(
                name=args.name.strip(),
                email=email,
                password_hash=hash_password(password),
                role=HR_ADMIN_ROLE,
            )
            session.add(record)
            print(f"Created HR_ADMIN account '{email}'.")
        else:
            record.role = HR_ADMIN_ROLE
            if not args.name.strip() == record.name:
                record.name = args.name.strip() or record.name
            print(f"Promoted '{email}' to HR_ADMIN (was {EMPLOYEE_ROLE}).")
        session.commit()
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

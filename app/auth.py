"""Production authentication and authorization (JWT + bcrypt + user DB).

Flow:

* ``POST /auth/register`` creates an ``EMPLOYEE`` account (bcrypt-hashed
  password; public registration can never create ``HR_ADMIN``).
* ``POST /auth/login`` verifies email + password and returns a JWT bearer
  token carrying the user id (``sub``).
* Every protected route depends on ``get_current_user``, which validates the
  ``Authorization: Bearer <token>`` header, reloads the user from the
  database (so role changes take effect immediately) and returns it.
  Missing/invalid/expired tokens yield HTTP 401.
* ``require_hr_admin`` additionally enforces the ``HR_ADMIN`` role on the
  backend (HTTP 403 otherwise). The React UI mirrors this, but the backend
  check is authoritative — manually crafted API calls are rejected too.

No demo identities, no hardcoded user lists, no client-supplied roles.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

import bcrypt
import jwt
from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_session
from app.exceptions import AuthenticationError, ForbiddenError
from app.models.user import (
    EMPLOYEE_ROLE,
    HR_ADMIN_ROLE,
    UserRecord,
    normalize_email,
)

Role = Literal["HR_ADMIN", "EMPLOYEE"]

HR_ROLE: Role = HR_ADMIN_ROLE


@dataclass(frozen=True)
class User:
    """The authenticated caller, freshly loaded from the users table."""

    id: int
    name: str
    email: str
    role: Role

    @property
    def is_hr(self) -> bool:
        return self.role == HR_ADMIN_ROLE


# ------------------------------------------------------------------ #
# Password hashing (bcrypt)
# ------------------------------------------------------------------ #
def hash_password(password: str) -> str:
    """Hash a plain-text password with bcrypt. Never store the input."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time bcrypt verification of a login attempt."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ------------------------------------------------------------------ #
# JWT tokens
# ------------------------------------------------------------------ #
def create_access_token(user_id: int) -> str:
    """Issue a signed JWT whose subject is the user id."""
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )
    payload = {"sub": str(user_id), "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _decode_token(token: str) -> int:
    """Validate a JWT and return the subject user id, or raise 401."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Session expired. Please log in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid authentication token.") from exc
    try:
        return int(payload.get("sub"))
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Invalid authentication token.") from exc


# ------------------------------------------------------------------ #
# FastAPI dependencies
# ------------------------------------------------------------------ #
def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: Session = Depends(get_session),
) -> User:
    """Authenticate the caller from ``Authorization: Bearer <jwt>`` (HTTP 401).

    The user (including the role) is reloaded from the database on every
    request, so role changes take effect immediately.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError(
            "Not authenticated. Log in with email and password."
        )
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise AuthenticationError("Not authenticated.")

    user_id = _decode_token(token)
    record = session.get(UserRecord, user_id)
    if record is None:
        raise AuthenticationError("Account no longer exists.")
    role = record.role if record.role in (HR_ADMIN_ROLE, EMPLOYEE_ROLE) else EMPLOYEE_ROLE
    return User(id=record.id, name=record.name, email=record.email, role=role)


def require_hr_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Allow only HR_ADMIN on the backend (HTTP 403 otherwise)."""
    if not user.is_hr:
        raise ForbiddenError(
            "Access denied: only HR_ADMIN users can access company-policy ingestion."
        )
    return user


def authenticate_user(session: Session, email: str, password: str) -> UserRecord:
    """Verify email + password, returning the record or raising 401."""
    record = session.execute(
        select(UserRecord).where(UserRecord.email == normalize_email(email))
    ).scalar_one_or_none()
    if record is None or not verify_password(password, record.password_hash):
        raise AuthenticationError("Invalid email or password.")
    return record


__all__ = [
    "Role",
    "User",
    "HR_ROLE",
    "EMPLOYEE_ROLE",
    "authenticate_user",
    "create_access_token",
    "get_current_user",
    "hash_password",
    "require_hr_admin",
    "verify_password",
]

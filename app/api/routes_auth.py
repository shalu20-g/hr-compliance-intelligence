"""Email + password authentication endpoints (JWT bearer tokens)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth import (
    User,
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
)
from app.exceptions import ConflictError
from app.models.user import (
    EMPLOYEE_ROLE,
    TokenResponse,
    UserLogin,
    UserOut,
    UserRecord,
    UserRegister,
    normalize_email,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserRegister, db: Annotated[Session, Depends(get_db)]) -> UserOut:
    """Create a new account. New registrations always receive EMPLOYEE role.

    There is intentionally no way to self-register as HR_ADMIN — the first
    HR_ADMIN account is created with ``scripts/create_admin.py``.
    """
    email = normalize_email(payload.email)
    existing = db.execute(
        select(UserRecord).where(UserRecord.email == email)
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"An account for '{email}' already exists.")

    record = UserRecord(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        role=EMPLOYEE_ROLE,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return UserOut(
        id=record.id,
        name=record.name,
        email=record.email,
        role=record.role,
        created_at=record.created_at,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    """Verify email + password and return a JWT bearer token."""
    record = authenticate_user(db, payload.email, payload.password)
    return TokenResponse(access_token=create_access_token(record.id))


@router.post("/logout")
def logout(user: Annotated[User, Depends(get_current_user)]) -> dict:
    """Log out (tokens are stateless — the client discards its token)."""
    return {"status": "ok", "user_id": user.id}


@router.get("/me", response_model=UserOut)
def who_am_i(user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    """Return the authenticated user's profile and server-side role."""
    return UserOut(id=user.id, name=user.name, email=user.email, role=user.role)

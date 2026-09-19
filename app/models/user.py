"""User account models: SQLAlchemy table + Pydantic API schemas.

Roles are exactly ``HR_ADMIN`` and ``EMPLOYEE``. Passwords are never stored
in plain text — only bcrypt hashes — and password hashes are never included
in API responses.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

HR_ADMIN_ROLE = "HR_ADMIN"
EMPLOYEE_ROLE = "EMPLOYEE"
VALID_ROLES = (HR_ADMIN_ROLE, EMPLOYEE_ROLE)


class UserRecord(Base):
    """The ``users`` table (PostgreSQL in production, SQLite for dev/test)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=EMPLOYEE_ROLE)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def normalize_email(email: str) -> str:
    return email.strip().lower()


class UserRegister(BaseModel):
    """Public registration payload. New accounts always become EMPLOYEE."""

    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        value = normalize_email(value)
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("email must be a valid email address")
        return value


class UserLogin(BaseModel):
    """Email + password login payload."""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _normalise(cls, value: str) -> str:
        return normalize_email(value)


class UserOut(BaseModel):
    """Public user representation. Never contains a password hash."""

    id: int
    name: str
    email: str
    role: str
    created_at: datetime | None = None


class TokenResponse(BaseModel):
    """Login response carrying the JWT bearer token."""

    access_token: str
    token_type: str = "bearer"


__all__ = [
    "HR_ADMIN_ROLE",
    "EMPLOYEE_ROLE",
    "VALID_ROLES",
    "UserRecord",
    "normalize_email",
    "UserRegister",
    "UserLogin",
    "UserOut",
    "TokenResponse",
]

"""
Pydantic v2 schemas for the Authentication module.

Covers user registration, login (JSON body), OAuth2 form login,
token responses, and the user read model.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    """Payload for registering a new user account."""

    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

    @field_validator("full_name")
    @classmethod
    def clean_full_name(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return v.strip()
        return v


# ---------------------------------------------------------------------------
# Login (JSON body — primary API contract)
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """JSON body payload for the login endpoint."""

    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.strip().lower()


# ---------------------------------------------------------------------------
# Token (response)
# ---------------------------------------------------------------------------

class TokenResponse(BaseModel):
    """JWT token response returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Internal model representing the claims inside a JWT."""

    sub: Optional[str] = None
    exp: Optional[int] = None


# ---------------------------------------------------------------------------
# User read model
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    """Public-facing user representation (no password fields)."""

    id: int
    email: str
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

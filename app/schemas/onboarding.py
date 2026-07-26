"""
Pydantic v2 schemas for the Onboarding module.

Covers the one-time bootstrap flow:
  POST /onboarding/complete  — OnboardingComplete (request)
  GET  /onboarding/status    — OnboardingStatusResponse (response)
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, field_validator


class OnboardingComplete(BaseModel):
    """Payload for completing business onboarding.

    Submitted exactly once per business, immediately after first login.
    Amounts must be non-negative; they seed the opening ledger entries.
    """

    business_name: str
    opening_cash: Decimal
    opening_float: Decimal

    @field_validator("business_name")
    @classmethod
    def clean_business_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("business_name must not be empty")
        return v

    @field_validator("opening_cash", "opening_float")
    @classmethod
    def non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Opening amounts must be non-negative")
        return v


class OnboardingStatusResponse(BaseModel):
    """Current onboarding state for the authenticated user's business."""

    completed: bool
    business_name: Optional[str] = None
    opening_cash: Optional[Decimal] = None
    opening_float: Optional[Decimal] = None
    onboarding_completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OnboardingCompleteResponse(BaseModel):
    """Returned after successfully completing onboarding."""

    message: str
    business_name: str
    onboarding_completed_at: datetime

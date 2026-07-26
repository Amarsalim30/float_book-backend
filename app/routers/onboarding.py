"""
Onboarding API router.

Endpoints:
  POST /onboarding/complete  — Run the one-time bootstrap (auth required).
  GET  /onboarding/status    — Check if onboarding is done (auth required).

Both endpoints require a valid Bearer token.  Onboarding always happens
after authentication — there is no anonymous onboarding path.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.onboarding import (
    OnboardingComplete,
    OnboardingCompleteResponse,
    OnboardingStatusResponse,
)
from app.services import onboarding_service

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


@router.get(
    "/status",
    response_model=OnboardingStatusResponse,
    summary="Get onboarding status",
)
def get_onboarding_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OnboardingStatusResponse:
    """Return whether the authenticated user has completed onboarding.

    The Flutter client calls this immediately after login to decide routing:
    - ``completed=false``  →  show the onboarding screen
    - ``completed=true``   →  go directly to the dashboard
    """
    return onboarding_service.get_status(db, current_user)


@router.post(
    "/complete",
    response_model=OnboardingCompleteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Complete onboarding (write-once)",
)
def complete_onboarding(
    request: OnboardingComplete,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OnboardingCompleteResponse:
    """Run the one-time onboarding bootstrap.

    Creates the Business record, seeds two opening ledger entries (cash and
    float), and permanently locks onboarding.  Calling this endpoint a second
    time returns **409 Conflict**.

    **Request body**:
    - ``business_name``: non-empty string
    - ``opening_cash``: non-negative decimal (e.g. 50000.00)
    - ``opening_float``: non-negative decimal (e.g. 20000.00)
    """
    return onboarding_service.complete_onboarding(db, current_user, request)

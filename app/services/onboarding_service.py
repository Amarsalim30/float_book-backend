"""
Onboarding service — business logic for the bootstrap onboarding flow.

Rules enforced here:
  1. Onboarding is write-once. If onboarding_completed is True, reject (409 Conflict).
  2. All DB writes (business + two ledger seeds + onboarding lock) happen inside
     a single atomic block. Any failure rolls back everything.
  3. Balances are seeded into the ledger, not stored as a running total.
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import delete
from fastapi import HTTPException, status

from app.models.user import User
from app.models.ledger_entry import LedgerEntry
from app.repositories import business_repository, ledger_repository
from app.schemas.onboarding import (
    OnboardingComplete,
    OnboardingStatusResponse,
    OnboardingCompleteResponse,
)

logger = logging.getLogger(__name__)


def get_status(db: Session, current_user: User) -> OnboardingStatusResponse:
    """Return the onboarding status for the authenticated user's business.

    Called by the Flutter client after every login to decide routing:
      completed=False  →  show onboarding screen
      completed=True   →  go to dashboard
    """
    business = business_repository.get_by_owner(db, current_user.id)

    if not business or not business.onboarding_completed:
        return OnboardingStatusResponse(completed=False)

    return OnboardingStatusResponse(
        completed=True,
        business_name=business.business_name,
        opening_cash=business.opening_cash,
        opening_float=business.opening_float,
        onboarding_completed_at=business.onboarding_completed_at,
    )


def complete_onboarding(
    db: Session,
    current_user: User,
    request: OnboardingComplete,
) -> OnboardingCompleteResponse:
    """Run the one-time onboarding bootstrap.

    Steps (all in one transaction):
      1. Guard: reject if onboarding already completed.
      2. Create or update Business record.
      3. Clean up any stale uncommitted seed entries for this business.
      4. Seed opening cash ledger entry.
      5. Seed opening float ledger entry.
      6. Mark onboarding complete (write-once lock).
      7. Commit.
    """
    try:
        business = business_repository.get_by_owner(db, current_user.id)

        # --- Guard: write-once ---
        if business and business.onboarding_completed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Onboarding has already been completed for this account.",
            )

        # --- Step 1: Create or update business ---
        if not business:
            business = business_repository.create(
                db, current_user.id, request.business_name
            )
        else:
            business.business_name = request.business_name
            db.add(business)
            db.flush()

        # --- Step 2: Clean up any prior seed entries if retrying ---
        db.execute(
            delete(LedgerEntry).where(
                LedgerEntry.business_id == business.id,
                LedgerEntry.entry_type == "seed",
            )
        )

        # --- Step 3 & 4: Seed ledger entries ---
        ledger_repository.create_seed_entry(
            db=db,
            business_id=business.id,
            account_type="cash",
            amount=request.opening_cash,
            created_by=current_user.id,
            description="Opening cash balance",
        )
        ledger_repository.create_seed_entry(
            db=db,
            business_id=business.id,
            account_type="float",
            amount=request.opening_float,
            created_by=current_user.id,
            description="Opening float balance",
        )

        # --- Step 5: Lock onboarding ---
        business = business_repository.mark_completed(
            db=db,
            business=business,
            opening_cash=request.opening_cash,
            opening_float=request.opening_float,
        )

        db.commit()
        db.refresh(business)

        return OnboardingCompleteResponse(
            message="Onboarding completed successfully.",
            business_name=business.business_name,
            onboarding_completed_at=business.onboarding_completed_at,
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error(
            "Onboarding completion failed for user_id=%s: %s",
            current_user.id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Onboarding failed: {exc}",
        ) from exc

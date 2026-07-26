"""
Business repository — all DB access for the Business model.

Kept intentionally thin: queries and mutations only, no business logic.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.business import Business


def get_by_owner(db: Session, user_id: int) -> Optional[Business]:
    """Return the Business owned by *user_id*, or None if it doesn't exist."""
    return db.query(Business).filter(Business.owner_id == user_id).first()


def create(db: Session, user_id: int, business_name: str) -> Business:
    """Insert a new Business record without flushing or committing.

    The caller is responsible for committing the transaction.
    """
    business = Business(owner_id=user_id, business_name=business_name)
    db.add(business)
    db.flush()  # get the PK before we need it for ledger entries
    return business


def mark_completed(
    db: Session,
    business: Business,
    opening_cash: Decimal,
    opening_float: Decimal,
) -> Business:
    """Stamp the onboarding lock and record the seed amounts.

    Does not commit — the caller owns the transaction boundary.
    """
    business.opening_cash = opening_cash
    business.opening_float = opening_float
    business.onboarding_completed = True
    business.onboarding_completed_at = datetime.now(timezone.utc)
    db.add(business)
    return business

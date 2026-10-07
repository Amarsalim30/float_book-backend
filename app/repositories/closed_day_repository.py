"""ClosedDay repository — DB access for closed_days table."""
from datetime import date
from decimal import Decimal
from typing import Optional, Tuple, List
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from app.models.closed_day import ClosedDay


def get_by_date(db: Session, business_id: int, closed_date: date) -> Optional[ClosedDay]:
    return (
        db.query(ClosedDay)
        .filter(
            ClosedDay.business_id == business_id,
            ClosedDay.closed_date == closed_date,
        )
        .first()
    )


def get_latest_before(db: Session, business_id: int, before_date: date) -> Optional[ClosedDay]:
    """Find the most recent closed day strictly before `before_date`."""
    return (
        db.query(ClosedDay)
        .filter(
            ClosedDay.business_id == business_id,
            ClosedDay.closed_date < before_date,
        )
        .order_by(desc(ClosedDay.closed_date))
        .first()
    )


def get_latest(db: Session, business_id: int) -> Optional[ClosedDay]:
    """Find the most recent closed day."""
    return (
        db.query(ClosedDay)
        .filter(ClosedDay.business_id == business_id)
        .order_by(desc(ClosedDay.closed_date))
        .first()
    )


def create(db: Session, closed_day: ClosedDay) -> ClosedDay:
    db.add(closed_day)
    db.flush()
    return closed_day


def get_by_id(db: Session, business_id: int, closed_day_id: int) -> Optional[ClosedDay]:
    return (
        db.query(ClosedDay)
        .filter(
            ClosedDay.id == closed_day_id,
            ClosedDay.business_id == business_id,
        )
        .first()
    )


def list_history(
    db: Session,
    business_id: int,
    page: int = 1,
    limit: int = 20,
) -> Tuple[List[ClosedDay], int, dict]:
    query = (
        db.query(ClosedDay)
        .filter(ClosedDay.business_id == business_id)
        .order_by(desc(ClosedDay.closed_date))
    )
    total = query.count()

    offset = (page - 1) * limit if page > 0 else 0
    items = query.offset(offset).limit(limit).all()

    # Aggregate stats
    total_closed = total
    balanced_count = (
        db.query(func.count(ClosedDay.id))
        .filter(
            ClosedDay.business_id == business_id,
            ClosedDay.status == "balanced",
        )
        .scalar()
        or 0
    )
    discrepancy_count = total_closed - balanced_count

    stats = {
        "total_closed_days": total_closed,
        "balanced_days": balanced_count,
        "discrepancy_days": discrepancy_count,
    }

    return items, total, stats

"""ClosedDay service — business logic for daily reconciliation and closing."""
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.closed_day import ClosedDay
from app.models.ledger_entry import LedgerEntry
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories import (
    business_repository,
    closed_day_repository,
    ledger_repository,
    transaction_repository,
)
from app.schemas.closed_day import (
    CloseDayHistoryResponse,
    CloseDayHistoryStats,
    CloseDayRequest,
    ClosedDayResponse,
    TodayReconciliationResponse,
)
from app.schemas.dashboard import ActivityItem, LedgerEffect

NAIROBI_TZ = ZoneInfo("Africa/Nairobi")


def _get_day_bounds_utc():
    now_nairobi = datetime.now(NAIROBI_TZ)
    day_start_nairobi = now_nairobi.replace(hour=0, minute=0, second=0, microsecond=0)
    day_start_utc = day_start_nairobi.astimezone(timezone.utc)
    today_date = now_nairobi.date()
    return today_date, day_start_utc


def get_today_reconciliation(db: Session, current_user: User) -> TodayReconciliationResponse:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found. Complete onboarding first.",
        )

    today_date, day_start_utc = _get_day_bounds_utc()
    existing = closed_day_repository.get_by_date(db, business.id, today_date)

    # 1. Opening balances (everything prior to today's start)
    cash_prior_in = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .filter(
            LedgerEntry.business_id == business.id,
            LedgerEntry.account_type == "cash",
            LedgerEntry.entry_type.in_(["seed", "credit"]),
            LedgerEntry.created_at < day_start_utc,
        )
        .scalar()
    )
    cash_prior_out = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .filter(
            LedgerEntry.business_id == business.id,
            LedgerEntry.account_type == "cash",
            LedgerEntry.entry_type == "debit",
            LedgerEntry.created_at < day_start_utc,
        )
        .scalar()
    )
    opening_cash = Decimal(str(cash_prior_in)) - Decimal(str(cash_prior_out))

    float_prior_in = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .filter(
            LedgerEntry.business_id == business.id,
            LedgerEntry.account_type == "float",
            LedgerEntry.entry_type.in_(["seed", "credit"]),
            LedgerEntry.created_at < day_start_utc,
        )
        .scalar()
    )
    float_prior_out = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .filter(
            LedgerEntry.business_id == business.id,
            LedgerEntry.account_type == "float",
            LedgerEntry.entry_type == "debit",
            LedgerEntry.created_at < day_start_utc,
        )
        .scalar()
    )
    opening_float = Decimal(str(float_prior_in)) - Decimal(str(float_prior_out))

    # 2. Today's movements (created_at >= day_start_utc)
    cash_in = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .filter(
            LedgerEntry.business_id == business.id,
            LedgerEntry.account_type == "cash",
            LedgerEntry.entry_type.in_(["seed", "credit"]),
            LedgerEntry.created_at >= day_start_utc,
        )
        .scalar()
    )
    cash_out = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .filter(
            LedgerEntry.business_id == business.id,
            LedgerEntry.account_type == "cash",
            LedgerEntry.entry_type == "debit",
            LedgerEntry.created_at >= day_start_utc,
        )
        .scalar()
    )
    cash_in = Decimal(str(cash_in))
    cash_out = Decimal(str(cash_out))
    expected_cash = opening_cash + cash_in - cash_out

    float_in = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .filter(
            LedgerEntry.business_id == business.id,
            LedgerEntry.account_type == "float",
            LedgerEntry.entry_type.in_(["seed", "credit"]),
            LedgerEntry.created_at >= day_start_utc,
        )
        .scalar()
    )
    float_out = (
        db.query(func.coalesce(func.sum(LedgerEntry.amount), 0))
        .filter(
            LedgerEntry.business_id == business.id,
            LedgerEntry.account_type == "float",
            LedgerEntry.entry_type == "debit",
            LedgerEntry.created_at >= day_start_utc,
        )
        .scalar()
    )
    float_in = Decimal(str(float_in))
    float_out = Decimal(str(float_out))
    expected_float = opening_float + float_in - float_out

    # 3. Today's transactions
    today_txns = transaction_repository.get_today_by_business(db, business.id, limit=50)
    activity_items = [
        ActivityItem(
            id=tx.id,
            type=tx.type,
            description=tx.description,
            amount=tx.amount,
            created_at=tx.created_at,
            direction="in" if any(le.entry_type == "credit" and le.account_type in ("cash", "float") for le in tx.ledger_entries) else "out",
            counterparty_name=tx.person.name if tx.person else None,
            effects=[
                LedgerEffect(
                    account_type=le.account_type,
                    direction=le.entry_type,
                    amount=le.amount,
                    tracked_account_name=le.tracked_account.name if le.tracked_account else None,
                )
                for le in tx.ledger_entries
            ],
        )
        for tx in today_txns
    ]

    return TodayReconciliationResponse(
        date=today_date,
        is_already_closed=existing is not None,
        opening_cash=opening_cash,
        opening_float=opening_float,
        cash_in=cash_in,
        cash_out=cash_out,
        expected_cash=expected_cash,
        float_in=float_in,
        float_out=float_out,
        expected_float=expected_float,
        today_transactions=activity_items,
    )


def close_day(db: Session, current_user: User, request: CloseDayRequest) -> ClosedDayResponse:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found. Complete onboarding first.",
        )

    # Compute today's expected numbers
    recon = get_today_reconciliation(db, current_user)
    target_date = request.closed_date or recon.date

    cash_variance = request.actual_cash - recon.expected_cash
    float_variance = request.actual_float - recon.expected_float

    is_balanced = (cash_variance == Decimal("0.00") and float_variance == Decimal("0.00"))
    day_status = "balanced" if is_balanced else "discrepancy"

    adj_tx = None
    if request.post_adjustment and not is_balanced:
        # Create an adjustment transaction
        adj_amount = abs(cash_variance) + abs(float_variance)
        adj_tx = Transaction(
            business_id=business.id,
            type="adjustment",
            amount=adj_amount,
            payment_method="cash" if cash_variance != Decimal("0.00") else "mpesa",
            description=f"Day close adjustment: {request.notes or 'Reconciliation discrepancy'}",
            created_by=current_user.id,
        )
        db.add(adj_tx)
        db.flush()

        # Add balancing ledger entries
        if cash_variance != Decimal("0.00"):
            ledger_repository.create_entry(
                db=db,
                business_id=business.id,
                account_type="cash",
                entry_type="credit" if cash_variance > Decimal("0.00") else "debit",
                amount=abs(cash_variance),
                created_by=current_user.id,
                description=f"Cash variance adjustment ({'surplus' if cash_variance > 0 else 'shortage'})",
                transaction_id=adj_tx.id,
            )
        if float_variance != Decimal("0.00"):
            ledger_repository.create_entry(
                db=db,
                business_id=business.id,
                account_type="float",
                entry_type="credit" if float_variance > Decimal("0.00") else "debit",
                amount=abs(float_variance),
                created_by=current_user.id,
                description=f"Float variance adjustment ({'surplus' if float_variance > 0 else 'shortage'})",
                transaction_id=adj_tx.id,
            )

    # Check if record already exists for this date
    existing = closed_day_repository.get_by_date(db, business.id, target_date)
    if existing:
        existing.opening_cash = recon.opening_cash
        existing.expected_cash = recon.expected_cash
        existing.actual_cash = request.actual_cash
        existing.cash_variance = cash_variance
        existing.opening_float = recon.opening_float
        existing.expected_float = recon.expected_float
        existing.actual_float = request.actual_float
        existing.float_variance = float_variance
        existing.status = day_status
        existing.notes = request.notes
        existing.post_adjustment = request.post_adjustment
        if adj_tx:
            existing.adjustment_transaction_id = adj_tx.id
        existing.closed_by = current_user.id
        db.flush()
        db.commit()
        db.refresh(existing)
        return ClosedDayResponse.model_validate(existing)
    else:
        closed_day = ClosedDay(
            business_id=business.id,
            closed_date=target_date,
            opening_cash=recon.opening_cash,
            expected_cash=recon.expected_cash,
            actual_cash=request.actual_cash,
            cash_variance=cash_variance,
            opening_float=recon.opening_float,
            expected_float=recon.expected_float,
            actual_float=request.actual_float,
            float_variance=float_variance,
            status=day_status,
            notes=request.notes,
            post_adjustment=request.post_adjustment,
            adjustment_transaction_id=adj_tx.id if adj_tx else None,
            closed_by=current_user.id,
        )
        closed_day_repository.create(db, closed_day)
        db.commit()
        db.refresh(closed_day)
        return ClosedDayResponse.model_validate(closed_day)


def get_history(
    db: Session,
    current_user: User,
    page: int = 1,
    limit: int = 20,
) -> CloseDayHistoryResponse:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found. Complete onboarding first.",
        )

    items, total, stats = closed_day_repository.list_history(
        db, business.id, page=page, limit=limit
    )

    total_pages = (total + limit - 1) // limit if limit > 0 else 1

    return CloseDayHistoryResponse(
        stats=CloseDayHistoryStats(**stats),
        items=[ClosedDayResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


def get_detail(db: Session, current_user: User, closed_day_id: int) -> ClosedDayResponse:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found.",
        )

    record = closed_day_repository.get_by_id(db, business.id, closed_day_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Close day record not found.",
        )

    return ClosedDayResponse.model_validate(record)

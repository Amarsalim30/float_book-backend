import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from datetime import datetime
from app.models.user import User
from app.models.transaction import Transaction
from app.models.ledger_entry import LedgerEntry
from app.repositories import business_repository, ledger_repository, mpesa_repository, transaction_repository
from app.schemas.enums import TransactionSource
from app.schemas.transaction import (
    LedgerEffectResponse,
    MpesaMessageSummary,
    PersonSummary,
    TransactionCreate,
    TransactionDetailResponse,
    TransactionList,
    TransactionResponse,
)


@dataclass
class EffectSpec:
    account_type: Literal["cash", "float"]
    direction: Literal["credit", "debit"]
    amount: Decimal


def _compute_effects(
    request: TransactionCreate,
) -> tuple[str | None, Decimal, Decimal, Decimal, list[EffectSpec]]:
    """Normalize payment method and compute the ledger effect specs for a request."""
    raw_pm = (request.payment_method or request.account_type or "").lower()
    if raw_pm in ("mpesa", "float"):
        payment_method = "mpesa"
    elif raw_pm == "cash":
        payment_method = "cash"
    else:
        payment_method = request.payment_method

    sale_amount = request.amount
    amount_received = sale_amount
    change_amount = Decimal("0.00")

    effects_spec: list[EffectSpec] = []

    if request.type == "sale":
        if not payment_method or payment_method not in ("cash", "mpesa"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="payment_method must be 'cash' or 'mpesa' for a sale",
            )

        if payment_method == "cash" and request.mpesa_message_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="M-Pesa SMS cannot be attached to a cash sale",
            )

        amount_received = (
            request.amount_received if request.amount_received is not None else sale_amount
        )

        if amount_received < sale_amount:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Amount received cannot be less than sale amount",
            )

        change_amount = amount_received - sale_amount

        if payment_method == "cash":
            effects_spec = [
                EffectSpec(account_type="cash", direction="credit", amount=sale_amount)
            ]
        else:  # mpesa
            effects_spec = [
                EffectSpec(account_type="float", direction="credit", amount=amount_received)
            ]
            if change_amount > 0:
                effects_spec.append(
                    EffectSpec(account_type="cash", direction="debit", amount=change_amount)
                )

    elif request.type == "expense":
        if not payment_method or payment_method not in ("cash", "mpesa"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="payment_method must be 'cash' or 'mpesa' for an expense",
            )
        ledger_account = "cash" if payment_method == "cash" else "float"
        effects_spec = [
            EffectSpec(account_type=ledger_account, direction="debit", amount=request.amount)
        ]

    elif request.type == "withdrawal":
        effects_spec = [
            EffectSpec(account_type="float", direction="credit", amount=request.amount),
            EffectSpec(account_type="cash", direction="debit", amount=request.amount),
        ]

    elif request.type == "add_float":
        effects_spec = [
            EffectSpec(account_type="float", direction="credit", amount=request.amount),
        ]

    elif request.type == "add_cash":
        effects_spec = [
            EffectSpec(account_type="cash", direction="credit", amount=request.amount),
        ]

    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Transaction type '{request.type}' is not yet supported",
        )

    return payment_method, sale_amount, amount_received, change_amount, effects_spec


def _link_mpesa_message(
    db: Session,
    business,
    request: TransactionCreate,
    transaction: Transaction,
) -> None:
    """Validate and link an M-Pesa SMS to a transaction, if one was provided."""
    if request.mpesa_message_id is None:
        return
    mpesa_msg = mpesa_repository.get_by_id(db, request.mpesa_message_id)
    if not mpesa_msg or mpesa_msg.business_id != business.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="M-Pesa message not found for business",
        )
    if request.type == "sale" and mpesa_msg.direction != "MONEY_RECEIVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only MONEY_RECEIVED SMS can be attached to a sale",
        )
    if mpesa_msg.transaction_id is not None and mpesa_msg.transaction_id != transaction.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMS is already linked to another transaction",
        )
    mpesa_msg.transaction_id = transaction.id


def create(db: Session, current_user: User, request: TransactionCreate) -> TransactionResponse:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found for user. Complete onboarding first.",
        )

    # Normalize payment method and compute ledger effects
    payment_method, sale_amount, amount_received, change_amount, effects_spec = (
        _compute_effects(request)
    )

    # Atomic DB Transaction Block
    try:
        transaction_data = {
            "business_id": business.id,
            "type": request.type,
            "amount": sale_amount,
            "amount_received": amount_received if request.type == "sale" else None,
            "change_amount": change_amount if request.type == "sale" else Decimal("0.00"),
            "payment_method": payment_method if request.type in ("sale", "expense") else None,
            "description": request.description,
            "reference": request.reference,
            "person_id": request.person_id,
            "created_by": current_user.id,
        }
        transaction = transaction_repository.create(db, transaction_data)

        # Create Ledger Entries
        for spec in effects_spec:
            ledger_repository.create_entry(
                db=db,
                business_id=business.id,
                account_type=spec.account_type,
                entry_type=spec.direction,
                amount=spec.amount,
                created_by=current_user.id,
                description=request.description or f"{request.type.replace('_', ' ').title()} entry",
                transaction_id=transaction.id,
            )

        # Link MpesaMessage if provided (for sale, withdrawal, or expense)
        _link_mpesa_message(db, business, request, transaction)

        db.commit()
        db.refresh(transaction)

        return _map_transaction_response(transaction)

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error(
            "Transaction recording failed for user_id=%s: %s",
            current_user.id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record transaction: {exc}",
        ) from exc


def update(
    db: Session,
    current_user: User,
    transaction_id: int,
    request: TransactionCreate,
) -> TransactionResponse:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found for user. Complete onboarding first.",
        )

    tx = transaction_repository.get_by_id(db, transaction_id)
    if not tx or tx.business_id != business.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    payment_method, sale_amount, amount_received, change_amount, effects_spec = (
        _compute_effects(request)
    )

    try:
        # Unlink a previously-attached SMS if we're switching to none or a different one
        if tx.mpesa_message and (
            request.mpesa_message_id is None
            or tx.mpesa_message.id != request.mpesa_message_id
        ):
            tx.mpesa_message.transaction_id = None

        # Replace the ledger effects (balances are derived from entries, so this reverses the old ones)
        db.query(LedgerEntry).filter(LedgerEntry.transaction_id == tx.id).delete(
            synchronize_session=False
        )

        tx.type = request.type
        tx.amount = sale_amount
        tx.amount_received = amount_received if request.type == "sale" else None
        tx.change_amount = change_amount if request.type == "sale" else Decimal("0.00")
        tx.payment_method = payment_method if request.type in ("sale", "expense") else None
        tx.description = request.description

        for spec in effects_spec:
            ledger_repository.create_entry(
                db=db,
                business_id=business.id,
                account_type=spec.account_type,
                entry_type=spec.direction,
                amount=spec.amount,
                created_by=current_user.id,
                description=request.description or f"{request.type.replace('_', ' ').title()} entry",
                transaction_id=tx.id,
            )

        _link_mpesa_message(db, business, request, tx)

        db.commit()
        db.refresh(tx)

        return _map_transaction_response(tx)

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error(
            "Transaction update failed for user_id=%s transaction_id=%s: %s",
            current_user.id,
            transaction_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update transaction: {exc}",
        ) from exc


def delete(db: Session, current_user: User, transaction_id: int) -> None:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found for user. Complete onboarding first.",
        )

    tx = transaction_repository.get_by_id(db, transaction_id)
    if not tx or tx.business_id != business.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    try:
        if tx.mpesa_message:
            tx.mpesa_message.transaction_id = None

        db.query(LedgerEntry).filter(LedgerEntry.transaction_id == tx.id).delete(
            synchronize_session=False
        )
        db.delete(tx)
        db.commit()

    except Exception as exc:
        db.rollback()
        logger.error(
            "Transaction delete failed for user_id=%s transaction_id=%s: %s",
            current_user.id,
            transaction_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete transaction: {exc}",
        ) from exc


def _map_transaction_response(tx: Transaction) -> TransactionResponse:
    person_summary = (
        PersonSummary(
            id=tx.person.id,
            name=tx.person.name,
            phone_number=tx.person.phone,
        )
        if tx.person
        else None
    )

    mpesa_summary = (
        MpesaMessageSummary(
            id=tx.mpesa_message.id,
            reference=tx.mpesa_message.reference,
            name=tx.mpesa_message.sender,
            phone=None,
            amount=tx.mpesa_message.amount,
            direction=tx.mpesa_message.direction,
            timestamp=tx.mpesa_message.message_timestamp,
        )
        if tx.mpesa_message
        else None
    )

    source = (
        TransactionSource.IMPORTED_MPESA
        if tx.mpesa_message
        else TransactionSource.MANUAL
    )

    has_notes = bool(tx.description and tx.description.strip())
    has_attachment = bool(tx.mpesa_message)

    effects_list = [
        LedgerEffectResponse(
            account_type=le.account_type,
            direction=le.entry_type,
            amount=le.amount,
            tracked_account_name=(
                le.tracked_account.name if le.tracked_account else None
            ),
        )
        for le in tx.ledger_entries
    ]

    return TransactionResponse(
        id=tx.id,
        type=tx.type,
        source=source,
        amount=tx.amount,
        amount_received=tx.amount_received,
        change_amount=tx.change_amount,
        payment_method=tx.payment_method,
        mpesa_message_id=tx.mpesa_message.id if tx.mpesa_message else None,
        description=tx.description,
        reference=tx.reference,
        person_id=tx.person_id,
        created_at=tx.created_at,
        person=person_summary,
        mpesa_message=mpesa_summary,
        has_notes=has_notes,
        has_attachment=has_attachment,
        effects=effects_list,
        ledger_effects=effects_list,
    )


def get_all(
    db: Session,
    current_user: User,
    page: int = 1,
    limit: int = 20,
    type: str | None = None,
    q: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort: str = "desc",
) -> TransactionList:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        return TransactionList(
            items=[],
            total=0,
            page=page,
            limit=limit,
            total_pages=0,
            has_next=False,
            has_previous=False,
        )

    items, total = transaction_repository.get_all(
        db,
        business_id=business.id,
        page=page,
        limit=limit,
        type=type,
        q=q,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
    )

    response_items = [_map_transaction_response(tx) for tx in items]
    total_pages = (total + limit - 1) // limit if limit > 0 else 1

    return TransactionList(
        items=response_items,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1,
    )


def get_by_id(db: Session, current_user: User, transaction_id: int) -> TransactionDetailResponse:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found",
        )

    tx = transaction_repository.get_by_id(db, transaction_id)
    if not tx or tx.business_id != business.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )

    base_resp = _map_transaction_response(tx)
    raw_sms = tx.mpesa_message.raw_text if tx.mpesa_message else None

    return TransactionDetailResponse(
        **base_resp.model_dump(),
        raw_sms_text=raw_sms,
    )


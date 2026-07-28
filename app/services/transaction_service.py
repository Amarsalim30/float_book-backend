import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models.user import User
from app.repositories import business_repository, ledger_repository, mpesa_repository, transaction_repository
from app.schemas.transaction import (
    LedgerEffectResponse,
    TransactionCreate,
    TransactionList,
    TransactionResponse,
)


@dataclass
class EffectSpec:
    account_type: Literal["cash", "float"]
    direction: Literal["credit", "debit"]
    amount: Decimal


def create(db: Session, current_user: User, request: TransactionCreate) -> TransactionResponse:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found for user. Complete onboarding first.",
        )

    # Normalize payment method or account type for all transaction types
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
            request.amount_received
            if request.amount_received is not None
            else sale_amount
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
        # Map payment method to the ledger account that gets debited:
        # cash -> cash debit, mpesa -> float debit
        ledger_account = "cash" if payment_method == "cash" else "float"
        effects_spec = [EffectSpec(account_type=ledger_account, direction="debit", amount=request.amount)]

    elif request.type == "withdrawal":
        effects_spec = [
            EffectSpec(account_type="float", direction="credit", amount=request.amount),
            EffectSpec(account_type="cash", direction="debit", amount=request.amount),
        ]

    elif request.type == "add_float":
        if request.account_type == "cash":
            effects_spec = [
                EffectSpec(account_type="cash", direction="debit", amount=request.amount),
                EffectSpec(account_type="float", direction="credit", amount=request.amount),
            ]
        else:
            effects_spec = [
                EffectSpec(account_type="float", direction="credit", amount=request.amount),
            ]

    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Transaction type '{request.type}' is not yet supported",
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
                description=request.description or f"{request.type.capitalize()} entry",
                transaction_id=transaction.id,
            )

        # Link MpesaMessage if provided (for sale, withdrawal, or expense)
        if request.mpesa_message_id is not None:
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
            if mpesa_msg.transaction_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="SMS is already linked to another transaction",
                )
            mpesa_msg.transaction_id = transaction.id

        db.commit()
        db.refresh(transaction)

        effects_response = [
            LedgerEffectResponse(
                account_type=le.account_type,
                direction=le.entry_type,
                amount=le.amount,
            )
            for le in transaction.ledger_entries
        ]

        return TransactionResponse(
            id=transaction.id,
            type=transaction.type,
            amount=transaction.amount,
            amount_received=transaction.amount_received,
            change_amount=transaction.change_amount,
            payment_method=transaction.payment_method,
            mpesa_message_id=request.mpesa_message_id,
            description=transaction.description,
            reference=transaction.reference,
            person_id=transaction.person_id,
            created_at=transaction.created_at,
            effects=effects_response,
        )

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


def get_all(
    db: Session,
    current_user: User,
    page: int = 1,
    limit: int = 20,
    type: str | None = None,
) -> TransactionList:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        return TransactionList(items=[], total=0, page=page, limit=limit)

    items, total = transaction_repository.get_all(
        db, business_id=business.id, page=page, limit=limit, type=type
    )

    response_items = [
        TransactionResponse(
            id=tx.id,
            type=tx.type,
            amount=tx.amount,
            amount_received=tx.amount_received,
            change_amount=tx.change_amount,
            payment_method=tx.payment_method,
            mpesa_message_id=tx.mpesa_message.id if tx.mpesa_message else None,
            description=tx.description,
            reference=tx.reference,
            person_id=tx.person_id,
            created_at=tx.created_at,
            effects=[
                LedgerEffectResponse(
                    account_type=le.account_type,
                    direction=le.entry_type,
                    amount=le.amount,
                )
                for le in tx.ledger_entries
            ],
        )
        for tx in items
    ]

    return TransactionList(
        items=response_items,
        total=total,
        page=page,
        limit=limit,
    )


def get_by_id(db: Session, current_user: User, transaction_id: int) -> TransactionResponse:
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

    return TransactionResponse(
        id=tx.id,
        type=tx.type,
        amount=tx.amount,
        amount_received=tx.amount_received,
        change_amount=tx.change_amount,
        payment_method=tx.payment_method,
        mpesa_message_id=tx.mpesa_message.id if tx.mpesa_message else None,
        description=tx.description,
        reference=tx.reference,
        person_id=tx.person_id,
        created_at=tx.created_at,
        effects=[
            LedgerEffectResponse(
                account_type=le.account_type,
                direction=le.entry_type,
                amount=le.amount,
            )
            for le in tx.ledger_entries
        ],
    )

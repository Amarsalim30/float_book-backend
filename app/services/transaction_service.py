from dataclasses import dataclass
from typing import Literal
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import business_repository, ledger_repository, transaction_repository
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


def _resolve_effects(request: TransactionCreate) -> list[EffectSpec]:
    match request.type:
        case "sale":
            account = request.account_type or "float"
            if account not in ("cash", "float"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="account_type must be 'cash' or 'float'",
                )
            return [EffectSpec(account_type=account, direction="credit")]

        case "expense":
            account = request.account_type or "cash"
            if account not in ("cash", "float"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="account_type must be 'cash' or 'float'",
                )
            return [EffectSpec(account_type=account, direction="debit")]

        case "withdrawal":
            # Customer withdraws cash from agent: Agent receives float (credit), gives cash (debit)
            return [
                EffectSpec(account_type="float", direction="credit"),
                EffectSpec(account_type="cash", direction="debit"),
            ]

        case "add_float":
            # Agent buys float: Agent gives cash (debit), receives float (credit)
            return [
                EffectSpec(account_type="cash", direction="debit"),
                EffectSpec(account_type="float", direction="credit"),
            ]

        case _:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Transaction type '{request.type}' is not yet supported",
            )


def create(db: Session, current_user: User, request: TransactionCreate) -> TransactionResponse:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found for user. Complete onboarding first.",
        )

    effects_spec = _resolve_effects(request)

    try:
        transaction_data = {
            "business_id": business.id,
            "type": request.type,
            "amount": request.amount,
            "description": request.description,
            "reference": request.reference,
            "person_id": request.person_id,
            "created_by": current_user.id,
        }
        transaction = transaction_repository.create(db, transaction_data)

        for spec in effects_spec:
            ledger_repository.create_entry(
                db=db,
                business_id=business.id,
                account_type=spec.account_type,
                entry_type=spec.direction,
                amount=request.amount,
                created_by=current_user.id,
                description=request.description or f"{request.type.capitalize()} entry",
                transaction_id=transaction.id,
            )

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

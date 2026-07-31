"""
Tracked Account service layer.

Business rules:
  - Give Money (Cash/Float → TrackedAccount): validates Cash/Float has sufficient
    balance using existing ledger_repository.get_balance(); no negative Cash/Float.
  - Get Money Back (TrackedAccount → Cash/Float): validates TrackedAccount balance
    using canonical tracked_account_repository.get_balance(); V1 never allows
    TrackedAccount balance to go below 0.
  - All validation + DB writes are inside a single atomic transaction block.
  - Domain exceptions are raised; HTTPException is NEVER raised here.
"""
import logging
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import (
    InsufficientTrackedBalanceError,
    TrackedAccountNotFoundError,
    TrackedAccountOwnershipError,
)
from app.models.ledger_entry import LedgerEntry
from app.models.transaction import Transaction
from app.repositories import business_repository, ledger_repository, tracked_account_repository
from app.schemas.tracked_account import (
    GetMoneyBackRequest,
    GiveMoneyRequest,
    LedgerHistoryEntry,
    TrackedAccountCreate,
    TrackedAccountDetail,
    TrackedAccountList,
    TrackedAccountResponse,
    TransferResponse,
)

logger = logging.getLogger(__name__)


def _get_business_or_raise(db: Session, owner_id: int):
    """Resolve the business for the current user, or raise 404."""
    business = business_repository.get_by_owner(db, owner_id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found. Complete onboarding first.",
        )
    return business


def create_account(
    db: Session,
    current_user,
    request: TrackedAccountCreate,
) -> TrackedAccountResponse:
    business = _get_business_or_raise(db, current_user.id)

    try:
        data = {
            "business_id": business.id,
            "name": request.name,
            "account_type": request.account_type,
            "phone": request.phone,
            "notes": request.notes,
            "created_by": current_user.id,
        }
        account = tracked_account_repository.create(db, data)
        db.flush()

        balance = tracked_account_repository.get_balance(db, business.id, account.id)
        db.commit()
        db.refresh(account)

        return TrackedAccountResponse(
            id=account.id,
            name=account.name,
            account_type=account.account_type,
            phone=account.phone,
            notes=account.notes,
            balance=balance,
            created_at=account.created_at,
        )

    except Exception:
        db.rollback()
        raise


def get_all_accounts(
    db: Session,
    current_user,
) -> TrackedAccountList:
    business = _get_business_or_raise(db, current_user.id)
    accounts = tracked_account_repository.get_all(db, business.id)

    items = [
        TrackedAccountResponse(
            id=a.id,
            name=a.name,
            account_type=a.account_type,
            phone=a.phone,
            notes=a.notes,
            balance=tracked_account_repository.get_balance(db, business.id, a.id),
            created_at=a.created_at,
        )
        for a in accounts
    ]

    return TrackedAccountList(items=items, total=len(items))


def get_account_detail(
    db: Session,
    current_user,
    account_id: int,
) -> TrackedAccountDetail:
    business = _get_business_or_raise(db, current_user.id)

    account = tracked_account_repository.get_by_id(db, business.id, account_id)
    if not account:
        raise TrackedAccountNotFoundError(account_id)

    balance = tracked_account_repository.get_balance(db, business.id, account_id)
    asc_entries = tracked_account_repository.get_all_ledger_history_asc(
        db, business.id, account_id
    )

    given = Decimal("0.00")
    returned = Decimal("0.00")
    running_balance = Decimal("0.00")
    history_with_running: list[LedgerHistoryEntry] = []
    last_transaction = asc_entries[-1].created_at if asc_entries else None

    for entry in asc_entries:
        amt = Decimal(str(entry.amount))
        if entry.entry_type == "credit":
            given += amt
            running_balance += amt
        elif entry.entry_type == "debit":
            returned += amt
            running_balance -= amt

        history_with_running.append(
            LedgerHistoryEntry(
                id=entry.id,
                entry_type=entry.entry_type,
                amount=amt,
                description=entry.description,
                created_at=entry.created_at,
                running_balance=running_balance,
            )
        )

    # Return newest entries first for presentation
    history_with_running.reverse()

    return TrackedAccountDetail(
        id=account.id,
        name=account.name,
        account_type=account.account_type,
        phone=account.phone,
        notes=account.notes,
        balance=balance,
        given=given,
        returned=returned,
        last_transaction=last_transaction,
        created_at=account.created_at,
        history=history_with_running,
    )



def give_money(
    db: Session,
    current_user,
    request: GiveMoneyRequest,
) -> TransferResponse:
    """
    Give Money: Cash/Float → TrackedAccount.

    Debit source operational account; Credit tracked account.
    """
    business = _get_business_or_raise(db, current_user.id)

    # Verify tracked account belongs to this business
    account = tracked_account_repository.get_by_id(
        db, business.id, request.tracked_account_id
    )
    if not account:
        raise TrackedAccountOwnershipError(request.tracked_account_id)

    # Validate source balance using existing repository (Cash/Float rules unchanged)
    source_balance = ledger_repository.get_balance(db, business.id, request.source_type)
    if request.amount > source_balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient {request.source_type} balance. "
                f"Available: KSh {source_balance:,.2f}, Requested: KSh {request.amount:,.2f}"
            ),
        )

    try:
        # Create Transaction record (type="transfer")
        txn = Transaction(
            business_id=business.id,
            type="transfer",
            amount=request.amount,
            description=request.note or f"Give money to {account.name}",
            created_by=current_user.id,
        )
        db.add(txn)
        db.flush()

        # Debit source (Cash or Float)
        db.add(
            LedgerEntry(
                business_id=business.id,
                transaction_id=txn.id,
                account_type=request.source_type,
                tracked_account_id=None,
                entry_type="debit",
                amount=request.amount,
                description=request.note or f"Give money to {account.name}",
                created_by=current_user.id,
            )
        )

        # Credit destination (TrackedAccount)
        db.add(
            LedgerEntry(
                business_id=business.id,
                transaction_id=txn.id,
                account_type="tracked",
                tracked_account_id=account.id,
                entry_type="credit",
                amount=request.amount,
                description=request.note or f"Give money to {account.name}",
                created_by=current_user.id,
            )
        )

        db.commit()

        return TransferResponse(
            transaction_id=txn.id,
            source_type=request.source_type,
            destination_type="tracked",
            amount=request.amount,
            tracked_account_id=account.id,
            tracked_account_name=account.name,
            note=request.note,
        )

    except Exception:
        db.rollback()
        raise


def get_money_back(
    db: Session,
    current_user,
    request: GetMoneyBackRequest,
) -> TransferResponse:
    """
    Get Money Back: TrackedAccount → Cash/Float.

    Debit tracked account; Credit destination operational account.
    """
    business = _get_business_or_raise(db, current_user.id)

    # Verify tracked account belongs to this business
    account = tracked_account_repository.get_by_id(
        db, business.id, request.tracked_account_id
    )
    if not account:
        raise TrackedAccountOwnershipError(request.tracked_account_id)

    # Validate TrackedAccount has enough balance (V1: never allow negative)
    tracked_balance = tracked_account_repository.get_balance(
        db, business.id, account.id
    )
    if request.amount > tracked_balance:
        raise InsufficientTrackedBalanceError(
            name=account.name,
            requested=float(request.amount),
            available=float(tracked_balance),
        )

    try:
        # Create Transaction record
        txn = Transaction(
            business_id=business.id,
            type="transfer",
            amount=request.amount,
            description=request.note or f"Get money back from {account.name}",
            created_by=current_user.id,
        )
        db.add(txn)
        db.flush()

        # Debit source (TrackedAccount)
        db.add(
            LedgerEntry(
                business_id=business.id,
                transaction_id=txn.id,
                account_type="tracked",
                tracked_account_id=account.id,
                entry_type="debit",
                amount=request.amount,
                description=request.note or f"Get money back from {account.name}",
                created_by=current_user.id,
            )
        )

        # Credit destination (Cash or Float)
        db.add(
            LedgerEntry(
                business_id=business.id,
                transaction_id=txn.id,
                account_type=request.destination_type,
                tracked_account_id=None,
                entry_type="credit",
                amount=request.amount,
                description=request.note or f"Get money back from {account.name}",
                created_by=current_user.id,
            )
        )

        db.commit()

        return TransferResponse(
            transaction_id=txn.id,
            source_type="tracked",
            destination_type=request.destination_type,
            amount=request.amount,
            tracked_account_id=account.id,
            tracked_account_name=account.name,
            note=request.note,
        )

    except Exception:
        db.rollback()
        raise

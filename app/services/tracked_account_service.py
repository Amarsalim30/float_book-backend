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
from app.models.tracked_account import TrackedAccount
from app.models.transaction import Transaction
from app.repositories import (
    business_repository,
    ledger_repository,
    mpesa_repository,
    person_repository,
    tracked_account_repository,
)
from app.schemas.tracked_account import (
    ContactPositionSummary,
    ContactTotals,
    ContactWithPositions,
    ContactWithPositionsList,
    GetMoneyBackRequest,
    GiveMoneyRequest,
    LedgerHistoryEntry,
    ReceiveMoneyRequest,
    ReturnMoneyRequest,
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
        account = tracked_account_repository.get_by_normalized_name_and_position(
            db, business.id, request.name, request.position_type
        )
        if account is not None:
            balance = tracked_account_repository.get_balance(db, business.id, account.id)
            return TrackedAccountResponse(
                id=account.id,
                name=account.name,
                account_type=account.account_type,
                position_type=account.position_type,
                person_id=account.person_id,
                phone=account.phone,
                notes=account.notes,
                balance=balance,
                created_at=account.created_at,
            )

        data = {
            "business_id": business.id,
            "name": request.name,
            "account_type": request.account_type,
            "position_type": request.position_type,
            "person_id": request.person_id,
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
            position_type=account.position_type,
            person_id=account.person_id,
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
            position_type=a.position_type,
            person_id=a.person_id,
            phone=a.phone,
            notes=a.notes,
            balance=tracked_account_repository.get_balance(db, business.id, a.id),
            created_at=a.created_at,
        )
        for a in accounts
    ]

    return TrackedAccountList(items=items, total=len(items))


def get_contacts_with_positions(
    db: Session,
    current_user,
) -> ContactWithPositionsList:
    """
    Return ALL tracked accounts grouped into contacts (the shape the Accounts
    screen renders). Backend owns the grouping + KPI totals — the UI is thin.

    Grouping: accounts sharing a person_id collapse into one contact; standalone
    accounts (no person) collapse by EXACT name (case-sensitive — "Amar" and
    "amar" are distinct accounts). A tracked + held pair with the same name
    merges into one dual-position contact. A same-position collision is never
    silently dropped: the second account gets its own contact.
    Positions are never netted.
    """
    business = _get_business_or_raise(db, current_user.id)
    accounts = tracked_account_repository.get_all(db, business.id)

    contacts: dict[str, dict] = {}
    order: list[str] = []

    for account in accounts:
        if account.person_id is not None:
            key = f"person_{account.person_id}"
        else:
            key = f"name_{account.name.strip()}"

        position_field = (
            "tracked_position"
            if account.position_type == "tracked"
            else "held_position"
        )

        contact = contacts.get(key)
        if contact is not None and contact[position_field] is not None:
            key = f"{key}#{account.id}"
            contact = None

        if contact is None:
            contact = {
                "person_id": account.person_id,
                "name": account.name,
                "phone": account.phone,
                "tracked_position": None,
                "held_position": None,
            }
            contacts[key] = contact
            order.append(key)

        contact[position_field] = ContactPositionSummary(
            account_id=account.id,
            balance=tracked_account_repository.get_balance(
                db, business.id, account.id
            ),
        )

    items = [ContactWithPositions(**contacts[key]) for key in order]

    tracked_total = Decimal("0.00")
    held_total = Decimal("0.00")
    tracked_count = 0
    held_count = 0
    for contact in items:
        if contact.tracked_position is not None:
            tracked_total += contact.tracked_position.balance
            tracked_count += 1
        if contact.held_position is not None:
            held_total += contact.held_position.balance
            held_count += 1

    return ContactWithPositionsList(
        items=items,
        total=len(items),
        totals=ContactTotals(
            tracked_total=tracked_total,
            held_total=held_total,
            tracked_count=tracked_count,
            held_count=held_count,
        ),
    )


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
        position_type=account.position_type,
        person_id=account.person_id,
        phone=account.phone,
        notes=account.notes,
        balance=balance,
        given=given,
        returned=returned,
        last_transaction=last_transaction,
        created_at=account.created_at,
        history=history_with_running,
    )


def resolve_position(
    db: Session,
    business_id: int,
    person_id: int | None,
    tracked_account_id: int | None,
    position_type: str,
) -> TrackedAccount | None:
    """Look up an existing position account for a person or tracked account ID."""
    if person_id is not None:
        account = tracked_account_repository.get_by_person_and_position(
            db, business_id, person_id, position_type
        )
        if account:
            return account

    if tracked_account_id is not None:
        account = tracked_account_repository.get_by_id(db, business_id, tracked_account_id)
        if account:
            if account.position_type == position_type:
                return account
            elif account.person_id is not None:
                return tracked_account_repository.get_by_person_and_position(
                    db, business_id, account.person_id, position_type
                )
            else:
                return tracked_account_repository.get_by_normalized_name_and_position(
                    db, business_id, account.name, position_type
                )
    return None


def create_position_if_missing(
    db: Session,
    business_id: int,
    person_id: int | None,
    tracked_account_id: int | None,
    position_type: str,
    creator_id: int,
) -> TrackedAccount:
    """Create a position account for a person/contact if it does not exist yet."""
    existing = resolve_position(db, business_id, person_id, tracked_account_id, position_type)
    if existing:
        return existing

    name = "Contact"
    phone = None
    account_type = "person"
    target_person_id = person_id

    if person_id is not None:
        person = person_repository.get_by_id(db, person_id)
        if not person:
            raise TrackedAccountOwnershipError(person_id)
        name = person.name
        phone = person.phone
    elif tracked_account_id is not None:
        ref_account = tracked_account_repository.get_by_id(db, business_id, tracked_account_id)
        if not ref_account:
            raise TrackedAccountOwnershipError(tracked_account_id)
        name = ref_account.name
        phone = ref_account.phone
        account_type = ref_account.account_type
        target_person_id = ref_account.person_id

    data = {
        "business_id": business_id,
        "person_id": target_person_id,
        "name": name,
        "account_type": account_type,
        "position_type": position_type,
        "phone": phone,
        "created_by": creator_id,
    }
    account = tracked_account_repository.create(db, data)
    db.flush()
    return account


def _link_mpesa_message(
    db: Session,
    business,
    mpesa_message_id: int | None,
    transaction: Transaction,
) -> None:
    """Validate and link an M-Pesa SMS to a transfer transaction, if provided."""
    if mpesa_message_id is None:
        return
    mpesa_msg = mpesa_repository.get_by_id(db, mpesa_message_id)
    if not mpesa_msg or mpesa_msg.business_id != business.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="M-Pesa message not found for business",
        )
    # Direction is not enforced server-side: the picker defaults to the
    # expected direction per transfer type but lets the user switch, so any
    # unused Take/Give SMS may be attached to any transfer.
    if mpesa_msg.transaction_id is not None and mpesa_msg.transaction_id != transaction.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMS is already linked to another transaction",
        )
    mpesa_msg.transaction_id = transaction.id



def give_money(
    db: Session,
    current_user,
    request: GiveMoneyRequest,
) -> TransferResponse:
    """
    Give Money: Cash/Float → TrackedAccount (Money I Track position).
    """
    business = _get_business_or_raise(db, current_user.id)

    # Resolve or create Money I Track position account
    account = create_position_if_missing(
        db,
        business.id,
        request.person_id,
        request.tracked_account_id,
        "tracked",
        current_user.id,
    )

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
        txn_kwargs = {
            "business_id": business.id,
            "type": "transfer",
            "amount": request.amount,
            "description": request.note or f"Give money to {account.name}",
            "created_by": current_user.id,
        }
        if request.created_at is not None:
            txn_kwargs["created_at"] = request.created_at
        txn = Transaction(**txn_kwargs)
        db.add(txn)
        db.flush()

        # Debit source (Cash or Float)
        entry1_kwargs = {
            "business_id": business.id,
            "transaction_id": txn.id,
            "account_type": request.source_type,
            "tracked_account_id": None,
            "entry_type": "debit",
            "amount": request.amount,
            "description": request.note or f"Give money to {account.name}",
            "created_by": current_user.id,
        }
        if request.created_at is not None:
            entry1_kwargs["created_at"] = request.created_at
        db.add(LedgerEntry(**entry1_kwargs))

        # Credit destination (TrackedAccount)
        entry2_kwargs = {
            "business_id": business.id,
            "transaction_id": txn.id,
            "account_type": "tracked",
            "tracked_account_id": account.id,
            "entry_type": "credit",
            "amount": request.amount,
            "description": request.note or f"Give money to {account.name}",
            "created_by": current_user.id,
        }
        if request.created_at is not None:
            entry2_kwargs["created_at"] = request.created_at
        db.add(LedgerEntry(**entry2_kwargs))

        _link_mpesa_message(db, business, request.mpesa_message_id, txn)

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
    Get Money Back: TrackedAccount → Cash/Float (Money I Track position).
    """
    business = _get_business_or_raise(db, current_user.id)

    account = create_position_if_missing(
        db,
        business.id,
        request.person_id,
        request.tracked_account_id,
        "tracked",
        current_user.id,
    )

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
        txn_kwargs = {
            "business_id": business.id,
            "type": "transfer",
            "amount": request.amount,
            "description": request.note or f"Get money back from {account.name}",
            "created_by": current_user.id,
        }
        if request.created_at is not None:
            txn_kwargs["created_at"] = request.created_at
        txn = Transaction(**txn_kwargs)
        db.add(txn)
        db.flush()

        # Debit source (TrackedAccount)
        entry1_kwargs = {
            "business_id": business.id,
            "transaction_id": txn.id,
            "account_type": "tracked",
            "tracked_account_id": account.id,
            "entry_type": "debit",
            "amount": request.amount,
            "description": request.note or f"Get money back from {account.name}",
            "created_by": current_user.id,
        }
        if request.created_at is not None:
            entry1_kwargs["created_at"] = request.created_at
        db.add(LedgerEntry(**entry1_kwargs))

        # Credit destination (Cash or Float)
        entry2_kwargs = {
            "business_id": business.id,
            "transaction_id": txn.id,
            "account_type": request.destination_type,
            "tracked_account_id": None,
            "entry_type": "credit",
            "amount": request.amount,
            "description": request.note or f"Get money back from {account.name}",
            "created_by": current_user.id,
        }
        if request.created_at is not None:
            entry2_kwargs["created_at"] = request.created_at
        db.add(LedgerEntry(**entry2_kwargs))

        _link_mpesa_message(db, business, request.mpesa_message_id, txn)

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


def receive_money(
    db: Session,
    current_user,
    request: ReceiveMoneyRequest,
) -> TransferResponse:
    """
    Receive Money: Contact → Cash/Float (Money Held position).

    Increases Money Held balance (+ credit entry) and Cash/Float (+ credit entry).
    """
    business = _get_business_or_raise(db, current_user.id)

    # Resolve or create Money Held position account
    account = create_position_if_missing(
        db,
        business.id,
        request.person_id,
        request.tracked_account_id,
        "held",
        current_user.id,
    )

    try:
        txn_kwargs = {
            "business_id": business.id,
            "type": "transfer",
            "amount": request.amount,
            "description": request.note or f"Receive money from {account.name}",
            "created_by": current_user.id,
        }
        if request.created_at is not None:
            txn_kwargs["created_at"] = request.created_at
        txn = Transaction(**txn_kwargs)
        db.add(txn)
        db.flush()

        # Credit destination Cash/Float (increases operational balance)
        entry1_kwargs = {
            "business_id": business.id,
            "transaction_id": txn.id,
            "account_type": request.destination_type,
            "tracked_account_id": None,
            "entry_type": "credit",
            "amount": request.amount,
            "description": request.note or f"Receive money from {account.name}",
            "created_by": current_user.id,
        }
        if request.created_at is not None:
            entry1_kwargs["created_at"] = request.created_at
        db.add(LedgerEntry(**entry1_kwargs))

        # Credit held position account (increases held balance)
        entry2_kwargs = {
            "business_id": business.id,
            "transaction_id": txn.id,
            "account_type": "tracked",
            "tracked_account_id": account.id,
            "entry_type": "credit",
            "amount": request.amount,
            "description": request.note or f"Receive money from {account.name}",
            "created_by": current_user.id,
        }
        if request.created_at is not None:
            entry2_kwargs["created_at"] = request.created_at
        db.add(LedgerEntry(**entry2_kwargs))

        _link_mpesa_message(db, business, request.mpesa_message_id, txn)

        db.commit()

        return TransferResponse(
            transaction_id=txn.id,
            source_type="contact",
            destination_type=request.destination_type,
            amount=request.amount,
            tracked_account_id=account.id,
            tracked_account_name=account.name,
            note=request.note,
        )

    except Exception:
        db.rollback()
        raise


def return_money(
    db: Session,
    current_user,
    request: ReturnMoneyRequest,
) -> TransferResponse:
    """
    Return Money: Cash/Float → Contact (Money Held position).

    Decreases Money Held balance (- debit entry) and Cash/Float (- debit entry).
    """
    business = _get_business_or_raise(db, current_user.id)

    account = create_position_if_missing(
        db,
        business.id,
        request.person_id,
        request.tracked_account_id,
        "held",
        current_user.id,
    )

    # Validate source operational Cash/Float balance
    source_balance = ledger_repository.get_balance(db, business.id, request.source_type)
    if request.amount > source_balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Insufficient {request.source_type} balance. "
                f"Available: KSh {source_balance:,.2f}, Requested: KSh {request.amount:,.2f}"
            ),
        )

    # Validate held account balance (never allow held balance to go below 0)
    held_balance = tracked_account_repository.get_balance(
        db, business.id, account.id
    )
    if request.amount > held_balance:
        raise InsufficientTrackedBalanceError(
            name=account.name,
            requested=float(request.amount),
            available=float(held_balance),
        )

    try:
        txn_kwargs = {
            "business_id": business.id,
            "type": "transfer",
            "amount": request.amount,
            "description": request.note or f"Return money to {account.name}",
            "created_by": current_user.id,
        }
        if request.created_at is not None:
            txn_kwargs["created_at"] = request.created_at
        txn = Transaction(**txn_kwargs)
        db.add(txn)
        db.flush()

        # Debit source Cash/Float (decreases operational balance)
        entry1_kwargs = {
            "business_id": business.id,
            "transaction_id": txn.id,
            "account_type": request.source_type,
            "tracked_account_id": None,
            "entry_type": "debit",
            "amount": request.amount,
            "description": request.note or f"Return money to {account.name}",
            "created_by": current_user.id,
        }
        if request.created_at is not None:
            entry1_kwargs["created_at"] = request.created_at
        db.add(LedgerEntry(**entry1_kwargs))

        # Debit held position account (decreases held balance)
        entry2_kwargs = {
            "business_id": business.id,
            "transaction_id": txn.id,
            "account_type": "tracked",
            "tracked_account_id": account.id,
            "entry_type": "debit",
            "amount": request.amount,
            "description": request.note or f"Return money to {account.name}",
            "created_by": current_user.id,
        }
        if request.created_at is not None:
            entry2_kwargs["created_at"] = request.created_at
        db.add(LedgerEntry(**entry2_kwargs))

        _link_mpesa_message(db, business, request.mpesa_message_id, txn)

        db.commit()


        return TransferResponse(
            transaction_id=txn.id,
            source_type=request.source_type,
            destination_type="contact",
            amount=request.amount,
            tracked_account_id=account.id,
            tracked_account_name=account.name,
            note=request.note,
        )

    except Exception:
        db.rollback()
        raise

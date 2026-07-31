"""
Tracked Accounts router — "Money I Track" & "Money Held" modules.

Endpoints:
  POST   /tracked-accounts/           Create a new tracked account
  GET    /tracked-accounts/           List all accounts with balances
  POST   /tracked-accounts/give       Give Money (Cash/Float → TrackedAccount)
  POST   /tracked-accounts/get-back   Get Money Back (TrackedAccount → Cash/Float)
  POST   /tracked-accounts/receive    Receive Money (Contact → Cash/Float)
  POST   /tracked-accounts/return     Return Money (Cash/Float → Contact)
  GET    /tracked-accounts/{id}       Detail + ledger history
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.exceptions import (
    InsufficientTrackedBalanceError,
    TrackedAccountNotFoundError,
    TrackedAccountOwnershipError,
)
from app.models.user import User
from app.schemas.tracked_account import (
    GetMoneyBackRequest,
    GiveMoneyRequest,
    ReceiveMoneyRequest,
    ReturnMoneyRequest,
    TrackedAccountCreate,
    TrackedAccountDetail,
    TrackedAccountList,
    TrackedAccountResponse,
    TransferResponse,
)
from app.services import tracked_account_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tracked-accounts", tags=["Tracked Accounts"])


# ---------------------------------------------------------------------------
# CRUD (List & Create)
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=TrackedAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tracked account (person, business, bank, or owner)",
)
def create_tracked_account(
    request: TrackedAccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return tracked_account_service.create_account(db, current_user, request)


@router.get(
    "/",
    response_model=TrackedAccountList,
    summary="List all tracked accounts with current balances",
)
def list_tracked_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return tracked_account_service.get_all_accounts(db, current_user)


# ---------------------------------------------------------------------------
# Transfers (Static routes MUST be declared before /{account_id})
# ---------------------------------------------------------------------------


@router.post(
    "/give",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Give Money — move Cash or Float to a tracked account",
)
def give_money(
    request: GiveMoneyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return tracked_account_service.give_money(db, current_user, request)
    except TrackedAccountOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/get-back",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Get Money Back — recover Cash or Float from a tracked account",
)
def get_money_back(
    request: GetMoneyBackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return tracked_account_service.get_money_back(db, current_user, request)
    except InsufficientTrackedBalanceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "insufficient_tracked_balance",
                "name": exc.name,
                "available": exc.available,
                "requested": exc.requested,
            },
        ) from exc
    except TrackedAccountOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/receive",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Receive Money — receive money from contact into Cash or Float (Money Held position)",
)
def receive_money(
    request: ReceiveMoneyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return tracked_account_service.receive_money(db, current_user, request)
    except TrackedAccountOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/return",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Return Money — return held money back to contact from Cash or Float (Money Held position)",
)
def return_money(
    request: ReturnMoneyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return tracked_account_service.return_money(db, current_user, request)
    except InsufficientTrackedBalanceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "insufficient_tracked_balance",
                "name": exc.name,
                "available": exc.available,
                "requested": exc.requested,
            },
        ) from exc
    except TrackedAccountOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Detail (Dynamic route /{account_id} placed LAST)
# ---------------------------------------------------------------------------


@router.get(
    "/{account_id}",
    response_model=TrackedAccountDetail,
    summary="Get a tracked account detail with ledger history",
)
def get_tracked_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return tracked_account_service.get_account_detail(db, current_user, account_id)
    except TrackedAccountNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

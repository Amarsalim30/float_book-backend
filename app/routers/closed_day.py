from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.closed_day import (
    CloseDayHistoryResponse,
    CloseDayRequest,
    ClosedDayResponse,
    TodayReconciliationResponse,
)
from app.services import closed_day_service

router = APIRouter(prefix="/close-day", tags=["Close Day"])


@router.get("/today", response_model=TodayReconciliationResponse)
def get_today_reconciliation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve today's reconciliation equations: opening balances, today's movements, and expected balances."""
    return closed_day_service.get_today_reconciliation(db, current_user)


@router.post("", response_model=ClosedDayResponse, status_code=status.HTTP_201_CREATED)
def post_close_day(
    request: CloseDayRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Post and lock a day's closing numbers with actual counts and optional variance adjustment."""
    return closed_day_service.close_day(db, current_user, request)


@router.get("/history", response_model=CloseDayHistoryResponse)
def get_close_day_history(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve paginated history of closed days and summary stats."""
    return closed_day_service.get_history(db, current_user, page=page, limit=limit)


@router.get("/{closed_day_id}", response_model=ClosedDayResponse)
def get_close_day_detail(
    closed_day_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve detail of a single closed day."""
    return closed_day_service.get_detail(db, current_user, closed_day_id)

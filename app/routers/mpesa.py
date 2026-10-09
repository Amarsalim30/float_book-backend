from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.mpesa import MpesaMessageCreate, MpesaMessageResponse
from app.services import mpesa_service

router = APIRouter(prefix="/mpesa", tags=["mpesa"])


@router.post("/messages", response_model=MpesaMessageResponse, status_code=status.HTTP_201_CREATED)
def ingest_message(
    payload: MpesaMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ingest a parsed M-Pesa SMS message for the current authenticated user's business."""
    return mpesa_service.create_message(db, current_user, payload)


@router.get("/messages", response_model=List[MpesaMessageResponse])
def get_recent_messages(
    direction: Optional[str] = Query(None),
    unused: bool = Query(True),
    limit: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get recent unused M-Pesa messages for manual selection when recording
    a transaction or transfer with SMS proof."""
    # ponytail: list without arbitrary 20 or le=100 hard cap
    return mpesa_service.get_recent_messages(
        db, current_user, direction=direction, unused=unused, limit=limit
    )

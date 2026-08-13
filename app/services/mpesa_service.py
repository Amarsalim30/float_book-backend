from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import business_repository, mpesa_repository
from app.schemas.mpesa import MpesaMessageCreate, MpesaMessageResponse


def create_message(
    db: Session, current_user: User, request: MpesaMessageCreate
) -> MpesaMessageResponse:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found. Complete onboarding first.",
        )

    message_data = {
        "business_id": business.id,
        "reference": request.reference,
        "sender": request.sender,
        "amount": request.amount,
        "direction": request.direction,
        "raw_text": request.raw_text,
        "message_timestamp": request.message_timestamp,
    }

    existing = mpesa_repository.get_by_reference(db, business.id, request.reference)
    if existing:
        return MpesaMessageResponse.model_validate(existing)

    try:
        message = mpesa_repository.create(db, message_data)
        db.commit()
        db.refresh(message)
        return MpesaMessageResponse.model_validate(message)
    except IntegrityError:
        db.rollback()
        existing = mpesa_repository.get_by_reference(db, business.id, request.reference)
        if existing:
            return MpesaMessageResponse.model_validate(existing)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Duplicate M-Pesa reference '{request.reference}'",
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest M-Pesa message: {exc}",
        ) from exc


def get_recent_messages(
    db: Session,
    current_user: User,
    direction: str = "MONEY_RECEIVED",
    unused: bool = True,
    limit: int = 20,
) -> list[MpesaMessageResponse]:
    business = business_repository.get_by_owner(db, current_user.id)
    if not business:
        return []

    if direction not in ("MONEY_RECEIVED", "MONEY_SENT"):
        return []

    messages = (
        mpesa_repository.get_recent_unused(
            db, business_id=business.id, direction=direction, limit=limit
        )
        if unused
        else []
    )

    return [MpesaMessageResponse.model_validate(msg) for msg in messages]

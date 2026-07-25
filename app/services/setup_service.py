from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.opening_balance import OpeningBalance
from app.schemas.opening_balance import OpeningBalanceCreate, OpeningBalanceResponse, SetupStatus


def get_status(db: Session) -> SetupStatus:
    opening_balance = db.query(OpeningBalance).first()
    
    if opening_balance:
        return SetupStatus(
            completed=True,
            opening_balance=opening_balance
        )
    
    return SetupStatus(completed=False)


def set_opening_balance(db: Session, request: OpeningBalanceCreate) -> OpeningBalanceResponse:
    existing = db.query(OpeningBalance).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Opening balance already exists"
        )
    
    opening_balance = OpeningBalance(
        cash=request.cash,
        float_amount=request.float_amount,
        bank=request.bank,
        mpesa=request.mpesa,
        notes=request.notes
    )
    
    db.add(opening_balance)
    db.commit()
    db.refresh(opening_balance)
    
    return opening_balance

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.opening_balance import OpeningBalanceCreate, OpeningBalanceResponse, SetupStatus
from app.services import setup_service

router = APIRouter(prefix="/setup", tags=["Setup"])


@router.get("/status", response_model=SetupStatus)
def get_setup_status(db: Session = Depends(get_db)):
    return setup_service.get_status(db)


@router.post("/opening-balance", response_model=OpeningBalanceResponse)
def set_opening_balance(request: OpeningBalanceCreate, db: Session = Depends(get_db)):
    return setup_service.set_opening_balance(db, request)

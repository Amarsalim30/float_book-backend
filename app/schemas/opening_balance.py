from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class OpeningBalanceCreate(BaseModel):
    cash: float
    float_amount: float
    bank: float = 0
    mpesa: float = 0
    notes: Optional[str] = None


class OpeningBalanceResponse(BaseModel):
    id: int
    cash: float
    float_amount: float
    bank: float
    mpesa: float
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class SetupStatus(BaseModel):
    completed: bool
    opening_balance: Optional[OpeningBalanceResponse] = None

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class TransactionCreate(BaseModel):
    type: str
    amount: float
    description: Optional[str] = None
    reference: Optional[str] = None
    person_id: Optional[int] = None


class TransactionResponse(BaseModel):
    id: int
    type: str
    amount: float
    description: Optional[str]
    reference: Optional[str]
    person_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionList(BaseModel):
    items: List[TransactionResponse]
    total: int
    page: int
    limit: int

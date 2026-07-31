from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class PersonCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    type: str  # customer, supplier, employee
    notes: Optional[str] = None


class PositionSummary(BaseModel):
    account_id: int
    balance: Decimal = Decimal("0.00")


class PersonResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None
    type: str
    notes: Optional[str] = None
    created_at: datetime
    money_i_track: Optional[PositionSummary] = None
    money_held: Optional[PositionSummary] = None

    model_config = {"from_attributes": True}


class PersonList(BaseModel):
    items: List[PersonResponse]
    total: int


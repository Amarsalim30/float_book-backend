from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PersonCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    type: str  # customer, supplier, employee
    notes: Optional[str] = None


class PersonResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str]
    type: str
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class PersonList(BaseModel):
    items: List[PersonResponse]
    total: int

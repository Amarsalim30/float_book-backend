from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, field_validator


class MpesaMessageCreate(BaseModel):
    reference: str
    sender: Optional[str] = None
    amount: Decimal
    direction: str  # MONEY_RECEIVED | MONEY_SENT | WITHDRAWAL | REVERSAL
    raw_text: str
    message_timestamp: datetime

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, v: str) -> str:
        allowed = {"MONEY_RECEIVED", "MONEY_SENT", "WITHDRAWAL", "REVERSAL"}
        if v not in allowed:
            raise ValueError(f"direction must be one of {allowed}")
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than 0")
        return v


class MpesaMessageResponse(BaseModel):
    id: int
    business_id: int
    reference: str
    sender: Optional[str] = None
    amount: Decimal
    direction: str
    raw_text: str
    message_timestamp: datetime
    transaction_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}

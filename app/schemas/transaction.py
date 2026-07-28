from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, field_validator


class TransactionCreate(BaseModel):
    type: str  # sale | expense | withdrawal | add_float | transfer | repayment | payment
    amount: Decimal  # Canonical Sale Amount for sales
    amount_received: Optional[Decimal] = None
    payment_method: Optional[str] = None  # "cash" | "mpesa"
    mpesa_message_id: Optional[int] = None
    account_type: Optional[str] = None  # "cash" | "float" for single-leg transactions (non-sales)
    description: Optional[str] = None
    reference: Optional[str] = None
    person_id: Optional[int] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {
            "sale",
            "expense",
            "withdrawal",
            "add_float",
            "transfer",
            "repayment",
            "payment",
        }
        if v not in allowed:
            raise ValueError(f"type must be one of {allowed}")
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than 0")
        return v

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("cash", "mpesa"):
            raise ValueError("payment_method must be 'cash' or 'mpesa'")
        return v


class LedgerEffectResponse(BaseModel):
    account_type: str  # "cash" | "float"
    direction: str  # "credit" | "debit"
    amount: Decimal


class TransactionResponse(BaseModel):
    id: int
    type: str
    amount: Decimal
    amount_received: Optional[Decimal] = None
    change_amount: Optional[Decimal] = None
    payment_method: Optional[str] = None
    mpesa_message_id: Optional[int] = None
    description: Optional[str] = None
    reference: Optional[str] = None
    person_id: Optional[int] = None
    created_at: datetime
    effects: List[LedgerEffectResponse] = []

    model_config = {"from_attributes": True}


class TransactionList(BaseModel):
    items: List[TransactionResponse]
    total: int
    page: int
    limit: int

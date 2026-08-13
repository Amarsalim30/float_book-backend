from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, field_validator

from app.schemas.enums import (
    AccountType,
    LedgerEntryType,
    MpesaDirection,
    PaymentMethod,
    TransactionSource,
    TransactionType,
)


class TransactionCreate(BaseModel):
    type: str  # sale | expense | withdrawal | add_float | add_cash | transfer | repayment | payment
    amount: Decimal  # Canonical Sale Amount for sales
    amount_received: Optional[Decimal] = None
    payment_method: Optional[str] = None  # "cash" | "mpesa"
    mpesa_message_id: Optional[int] = None
    mpesa_message_ids: Optional[List[int]] = None  # batch proofs (sales)
    account_type: Optional[str] = None  # "cash" | "float" for single-leg transactions (non-sales)
    description: Optional[str] = None
    reference: Optional[str] = None
    person_id: Optional[int] = None
    created_at: Optional[datetime] = None


    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {
            "sale",
            "expense",
            "withdrawal",
            "add_float",
            "add_cash",
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


class PersonSummary(BaseModel):
    id: int
    name: str
    phone_number: Optional[str] = None

    model_config = {"from_attributes": True}


class MpesaMessageSummary(BaseModel):
    id: int
    reference: str
    name: Optional[str] = None
    phone: Optional[str] = None
    amount: Decimal
    direction: MpesaDirection
    timestamp: datetime

    model_config = {"from_attributes": True}


class LedgerEffectResponse(BaseModel):
    account_type: AccountType
    direction: LedgerEntryType
    amount: Decimal
    tracked_account_name: Optional[str] = None

    model_config = {"from_attributes": True}


class TransactionResponse(BaseModel):
    id: int
    type: TransactionType
    source: TransactionSource = TransactionSource.MANUAL
    amount: Decimal
    amount_received: Optional[Decimal] = None
    change_amount: Optional[Decimal] = None
    payment_method: Optional[PaymentMethod] = None
    mpesa_message_id: Optional[int] = None
    description: Optional[str] = None
    reference: Optional[str] = None
    person_id: Optional[int] = None
    created_at: datetime
    person: Optional[PersonSummary] = None
    mpesa_message: Optional[MpesaMessageSummary] = None
    mpesa_messages: List[MpesaMessageSummary] = []
    has_notes: bool = False
    has_attachment: bool = False
    effects: List[LedgerEffectResponse] = []
    ledger_effects: List[LedgerEffectResponse] = []

    model_config = {"from_attributes": True}


class TransactionDetailResponse(TransactionResponse):
    raw_sms_text: Optional[str] = None
    raw_sms_texts: List[str] = []


class TransactionList(BaseModel):
    items: List[TransactionResponse]
    total: int
    page: int
    limit: int
    total_pages: int = 1
    has_next: bool = False
    has_previous: bool = False

from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, field_validator

AccountTypeEnum = Literal["person", "business", "bank", "owner"]
TransferSourceEnum = Literal["cash", "float", "tracked"]


class TrackedAccountCreate(BaseModel):
    name: str
    account_type: AccountTypeEnum = "person"
    phone: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be blank")
        return v.strip()


class TrackedAccountResponse(BaseModel):
    id: int
    name: str
    account_type: str
    phone: Optional[str] = None
    notes: Optional[str] = None
    balance: Decimal  # V1: always >= 0 ("holding for you")
    created_at: datetime

    model_config = {"from_attributes": True}


class TrackedAccountList(BaseModel):
    items: List[TrackedAccountResponse]
    total: int


class LedgerHistoryEntry(BaseModel):
    id: int
    entry_type: str        # "credit" | "debit"
    amount: Decimal
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TrackedAccountDetail(TrackedAccountResponse):
    history: List[LedgerHistoryEntry] = []


# ---------------------------------------------------------------------------
# Transfer request schemas
# ---------------------------------------------------------------------------

class GiveMoneyRequest(BaseModel):
    """
    Give Money: Cash/Float → TrackedAccount
    """
    source_type: Literal["cash", "float"]
    tracked_account_id: int
    amount: Decimal
    note: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than 0")
        return v


class GetMoneyBackRequest(BaseModel):
    """
    Get Money Back: TrackedAccount → Cash/Float
    """
    tracked_account_id: int
    destination_type: Literal["cash", "float"]
    amount: Decimal
    note: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than 0")
        return v


class TransferResponse(BaseModel):
    transaction_id: int
    source_type: str
    destination_type: str
    amount: Decimal
    tracked_account_id: int
    tracked_account_name: str
    note: Optional[str] = None

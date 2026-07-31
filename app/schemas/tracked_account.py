from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, field_validator

AccountTypeEnum = Literal["person", "business", "bank", "owner"]
TransferSourceEnum = Literal["cash", "float", "tracked"]


class TrackedAccountCreate(BaseModel):
    name: str
    account_type: AccountTypeEnum = "person"
    position_type: Literal["tracked", "held"] = "tracked"
    person_id: Optional[int] = None
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
    position_type: str = "tracked"
    person_id: Optional[int] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    balance: Decimal  # V1: always >= 0
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
    running_balance: Decimal = Decimal("0.00")

    model_config = {"from_attributes": True}


class TrackedAccountDetail(TrackedAccountResponse):
    given: Decimal = Decimal("0.00")
    returned: Decimal = Decimal("0.00")
    last_transaction: Optional[datetime] = None
    history: List[LedgerHistoryEntry] = []



# ---------------------------------------------------------------------------
# Transfer request schemas
# ---------------------------------------------------------------------------

class GiveMoneyRequest(BaseModel):
    """
    Give Money: Cash/Float → TrackedAccount (Money I Track)
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
    Get Money Back: TrackedAccount → Cash/Float (Money I Track)
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


class ReceiveMoneyRequest(BaseModel):
    """
    Receive Money: Contact → Cash/Float (Money Held - increases held balance & cash/float)
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


class ReturnMoneyRequest(BaseModel):
    """
    Return Money: Cash/Float → Contact (Money Held - decreases held balance & cash/float)
    """
    tracked_account_id: int
    source_type: Literal["cash", "float"]
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


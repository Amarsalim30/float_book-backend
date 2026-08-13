from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, field_validator, model_validator

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
    person_id: Optional[int] = None
    tracked_account_id: Optional[int] = None
    amount: Decimal
    note: Optional[str] = None
    mpesa_message_id: Optional[int] = None
    created_at: Optional[datetime] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than 0")
        return v

    @model_validator(mode="after")
    def check_target_identity(self):
        if self.person_id is None and self.tracked_account_id is None:
            raise ValueError("Either person_id or tracked_account_id must be provided")
        return self


class GetMoneyBackRequest(BaseModel):
    """
    Get Money Back: TrackedAccount → Cash/Float (Money I Track)
    """
    destination_type: Literal["cash", "float"]
    person_id: Optional[int] = None
    tracked_account_id: Optional[int] = None
    amount: Decimal
    note: Optional[str] = None
    mpesa_message_id: Optional[int] = None
    created_at: Optional[datetime] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than 0")
        return v

    @model_validator(mode="after")
    def check_target_identity(self):
        if self.person_id is None and self.tracked_account_id is None:
            raise ValueError("Either person_id or tracked_account_id must be provided")
        return self


class ReceiveMoneyRequest(BaseModel):
    """
    Receive Money: Contact → Cash/Float (Money Held - increases held balance & cash/float)
    """
    destination_type: Literal["cash", "float"]
    person_id: Optional[int] = None
    tracked_account_id: Optional[int] = None
    amount: Decimal
    note: Optional[str] = None
    mpesa_message_id: Optional[int] = None
    created_at: Optional[datetime] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than 0")
        return v

    @model_validator(mode="after")
    def check_target_identity(self):
        if self.person_id is None and self.tracked_account_id is None:
            raise ValueError("Either person_id or tracked_account_id must be provided")
        return self


class ReturnMoneyRequest(BaseModel):
    """
    Return Money: Cash/Float → Contact (Money Held - decreases held balance & cash/float)
    """
    source_type: Literal["cash", "float"]
    person_id: Optional[int] = None
    tracked_account_id: Optional[int] = None
    amount: Decimal
    note: Optional[str] = None
    mpesa_message_id: Optional[int] = None
    created_at: Optional[datetime] = None


    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be greater than 0")
        return v

    @model_validator(mode="after")
    def check_target_identity(self):
        if self.person_id is None and self.tracked_account_id is None:
            raise ValueError("Either person_id or tracked_account_id must be provided")
        return self


class TransferResponse(BaseModel):
    transaction_id: int
    source_type: str
    destination_type: str
    amount: Decimal
    tracked_account_id: int
    tracked_account_name: str
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Contacts-with-positions (backend-derived grouping, thin UI)
# ---------------------------------------------------------------------------

class ContactPositionSummary(BaseModel):
    account_id: int
    balance: Decimal = Decimal("0.00")


class ContactWithPositions(BaseModel):
    person_id: Optional[int] = None
    name: str
    phone: Optional[str] = None
    tracked_position: Optional[ContactPositionSummary] = None  # Money I Track
    held_position: Optional[ContactPositionSummary] = None     # Money Held


class ContactTotals(BaseModel):
    tracked_total: Decimal = Decimal("0.00")
    held_total: Decimal = Decimal("0.00")
    tracked_count: int = 0
    held_count: int = 0


class ContactWithPositionsList(BaseModel):
    items: List[ContactWithPositions]
    total: int
    totals: ContactTotals


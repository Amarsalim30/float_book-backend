from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel

from app.schemas.enums import AccountType, LedgerEntryType, TransactionType


class LedgerEntryStatementResponse(BaseModel):
    id: int
    created_at: datetime
    account_type: AccountType
    entry_type: LedgerEntryType
    amount: Decimal
    debit_amount: Optional[Decimal] = None
    credit_amount: Optional[Decimal] = None
    running_balance: Decimal
    transaction_id: Optional[int] = None
    transaction_type: Optional[TransactionType] = None
    description: Optional[str] = None
    reference: Optional[str] = None

    model_config = {"from_attributes": True}


class LedgerStatementResponse(BaseModel):
    account_type: AccountType
    current_balance: Decimal
    total_credits: Decimal
    total_debits: Decimal
    today_net: Decimal
    items: List[LedgerEntryStatementResponse]
    total: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_previous: bool

    model_config = {"from_attributes": True}

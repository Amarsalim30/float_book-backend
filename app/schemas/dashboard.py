from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel


class LedgerEffect(BaseModel):
    account_type: str  # "cash" | "float" | "tracked"
    direction: str  # "credit" | "debit"
    amount: Decimal
    tracked_account_name: Optional[str] = None


class ActivityItem(BaseModel):
    id: int
    type: str  # "sale" | "expense" | "withdrawal" | "add_float" | "add_cash"
    description: Optional[str] = None
    amount: Decimal
    created_at: datetime
    effects: List[LedgerEffect]


class DashboardResponse(BaseModel):
    business_name: str
    cash_balance: Decimal
    float_balance: Decimal
    today_activity: List[ActivityItem]
    day_closed: bool = False
    closing_variance: Optional[Decimal] = None

from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional
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

    # Display helpers computed by the backend so the UI stays thin.
    # "in" = money entering operational accounts, "out" = money leaving them.
    direction: Literal["in", "out"] = "in"

    # The other party to a transfer (tracked account name); else person name if any.
    counterparty_name: Optional[str] = None


class DashboardResponse(BaseModel):
    business_name: str
    cash_balance: Decimal
    float_balance: Decimal
    today_activity: List[ActivityItem]
    day_closed: bool = False
    day_status: Optional[str] = None  # "balanced" | "discrepancy"
    closing_variance: Optional[Decimal] = None
    closing_cash_variance: Optional[Decimal] = None
    closing_float_variance: Optional[Decimal] = None
    unrecorded_mpesa_count: int = 0
    unrecorded_mpesa_total: Decimal = Decimal("0.00")

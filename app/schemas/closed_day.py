from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.dashboard import ActivityItem


class TodayReconciliationResponse(BaseModel):
    date: date
    is_already_closed: bool
    opening_cash: Decimal
    opening_float: Decimal
    cash_in: Decimal
    cash_out: Decimal
    expected_cash: Decimal
    float_in: Decimal
    float_out: Decimal
    expected_float: Decimal
    today_transactions: List[ActivityItem] = Field(default_factory=list)


class CloseDayRequest(BaseModel):
    closed_date: Optional[date] = None
    actual_cash: Decimal = Field(..., ge=0)
    actual_float: Decimal = Field(..., ge=0)
    notes: Optional[str] = None
    post_adjustment: bool = False


class ClosedDayResponse(BaseModel):
    id: int
    business_id: int
    closed_date: date
    opening_cash: Decimal
    expected_cash: Decimal
    actual_cash: Decimal
    cash_variance: Decimal
    opening_float: Decimal
    expected_float: Decimal
    actual_float: Decimal
    float_variance: Decimal
    status: str
    notes: Optional[str] = None
    post_adjustment: bool = False
    adjustment_transaction_id: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CloseDayHistoryStats(BaseModel):
    total_closed_days: int
    balanced_days: int
    discrepancy_days: int


class CloseDayHistoryResponse(BaseModel):
    stats: CloseDayHistoryStats
    items: List[ClosedDayResponse]
    total: int
    page: int
    limit: int
    total_pages: int

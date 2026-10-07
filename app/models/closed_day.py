"""ClosedDay model — daily reconciliation checkpoints for cash and float.

Stores expected vs actual counts, variance, notes, and optional adjustment link.
ponytail: simple single table, no unneeded abstractions.
"""
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ClosedDay(Base):
    __tablename__ = "closed_days"

    __table_args__ = (
        UniqueConstraint("business_id", "closed_date", name="uq_closed_days_business_date"),
        Index("ix_closed_days_business_date", "business_id", "closed_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    closed_date = Column(Date, nullable=False)

    # Cash in Till
    opening_cash = Column(Numeric(14, 2), nullable=False)
    expected_cash = Column(Numeric(14, 2), nullable=False)
    actual_cash = Column(Numeric(14, 2), nullable=False)
    cash_variance = Column(Numeric(14, 2), nullable=False, default=0.00)

    # M-Pesa Float
    opening_float = Column(Numeric(14, 2), nullable=False)
    expected_float = Column(Numeric(14, 2), nullable=False)
    actual_float = Column(Numeric(14, 2), nullable=False)
    float_variance = Column(Numeric(14, 2), nullable=False, default=0.00)

    # Status: "balanced" | "discrepancy"
    status = Column(String, nullable=False, default="balanced")
    notes = Column(Text, nullable=True)

    post_adjustment = Column(Boolean, nullable=False, default=False)
    adjustment_transaction_id = Column(
        Integer, ForeignKey("transactions.id"), nullable=True, index=True
    )

    closed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    business = relationship("Business")
    creator = relationship("User", foreign_keys=[closed_by])
    adjustment_transaction = relationship(
        "Transaction", foreign_keys=[adjustment_transaction_id]
    )

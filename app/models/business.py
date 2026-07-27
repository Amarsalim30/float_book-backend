"""
Business model.

One Business per User (owner_id is UNIQUE).  Opening balances are stored here
as a convenience snapshot after onboarding completion, but balances are
*derived* from ledger_entries — these fields are write-once seed values.
"""
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Business(Base):
    __tablename__ = "businesses"

    __table_args__ = (
        UniqueConstraint("owner_id", name="uq_businesses_owner_id"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # 1 user → 1 business (MVP scope)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    business_name = Column(String, nullable=False)

    # Write-once seed values captured at onboarding time (for audit reference)
    opening_cash = Column(Numeric(14, 2), nullable=True)
    opening_float = Column(Numeric(14, 2), nullable=True)

    # Onboarding lock — once True this row is permanently sealed for onboarding
    onboarding_completed = Column(Boolean, nullable=False, default=False)
    onboarding_completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner = relationship("User", backref="business", uselist=False)
    ledger_entries = relationship("LedgerEntry", back_populates="business")
    transactions = relationship("Transaction", back_populates="business")


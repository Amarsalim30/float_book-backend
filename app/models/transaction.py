from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    __table_args__ = (
        Index(
            "ix_transactions_business_created",
            "business_id",
            "created_at",
            "id",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    type = Column(String, nullable=False)  # sale, expense, withdrawal, add_float, add_cash, transfer, etc.
    amount = Column(Numeric(14, 2), nullable=False)
    amount_received = Column(Numeric(14, 2), nullable=True)
    change_amount = Column(Numeric(14, 2), nullable=True, default=0.00)
    payment_method = Column(String, nullable=True)  # cash | mpesa
    description = Column(String, nullable=True)
    reference = Column(String, nullable=True)
    person_id = Column(Integer, ForeignKey("people.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    business = relationship("Business", back_populates="transactions")
    person = relationship("Person", back_populates="transactions")
    ledger_entries = relationship("LedgerEntry", back_populates="transaction")
    mpesa_messages = relationship("MpesaMessage", back_populates="transaction")

    @property
    def mpesa_message(self) -> "MpesaMessage | None":
        """First attached SMS (backward-compat accessor for single-proof flows)."""
        return self.mpesa_messages[0] if self.mpesa_messages else None


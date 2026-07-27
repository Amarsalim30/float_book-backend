from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    type = Column(String, nullable=False)  # sale, expense, withdrawal, add_float, transfer, etc.
    amount = Column(Numeric(14, 2), nullable=False)
    description = Column(String, nullable=True)
    reference = Column(String, nullable=True)
    person_id = Column(Integer, ForeignKey("people.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    business = relationship("Business", back_populates="transactions")
    person = relationship("Person", back_populates="transactions")
    ledger_entries = relationship("LedgerEntry", back_populates="transaction")


from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class MpesaMessage(Base):
    __tablename__ = "mpesa_messages"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    reference = Column(String, nullable=False, index=True)
    sender = Column(String, nullable=True)
    amount = Column(Numeric(14, 2), nullable=False)
    direction = Column(String, nullable=False)  # MONEY_RECEIVED, MONEY_SENT, WITHDRAWAL, REVERSAL
    raw_text = Column(String, nullable=False)
    message_timestamp = Column(DateTime(timezone=True), nullable=False)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    business = relationship("Business", back_populates="mpesa_messages")
    transaction = relationship("Transaction", back_populates="mpesa_message")

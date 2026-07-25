from sqlalchemy import Column, Integer, Float, DateTime, String
from sqlalchemy.sql import func
from app.core.database import Base


class OpeningBalance(Base):
    __tablename__ = "opening_balances"

    id = Column(Integer, primary_key=True, index=True)
    cash = Column(Float, nullable=False, default=0)
    float_amount = Column(Float, nullable=False, default=0)
    bank = Column(Float, nullable=False, default=0)
    mpesa = Column(Float, nullable=False, default=0)
    notes = Column(String)
    is_closed = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, and_
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Person(Base):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String)
    type = Column(String, nullable=False)  # customer, supplier, employee
    notes = Column(String)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    transactions = relationship("Transaction", back_populates="person")
    tracked_accounts = relationship("TrackedAccount", back_populates="person")

    tracked_account = relationship(
        "TrackedAccount",
        primaryjoin="and_(Person.id==TrackedAccount.person_id, TrackedAccount.position_type=='tracked')",
        uselist=False,
        overlaps="tracked_accounts",
    )
    held_account = relationship(
        "TrackedAccount",
        primaryjoin="and_(Person.id==TrackedAccount.person_id, TrackedAccount.position_type=='held')",
        uselist=False,
        overlaps="tracked_account,tracked_accounts",
    )



"""
TrackedAccount model — represents a person, business, bank, or owner
that temporarily holds money on behalf of the business.

V1 purpose: Track money moved out of Cash/Float that the business expects
to recover. Balance is ALWAYS >= 0.

account_type values:
  person   — individual (e.g. "Amar", "John")
  business — company / supplier (e.g. "Supplier ABC")
  bank     — bank account (e.g. "Equity Bank")
  owner    — business owner personal account
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class TrackedAccount(Base):
    __tablename__ = "tracked_accounts"
    __table_args__ = (
        UniqueConstraint("person_id", "position_type", name="uq_person_position"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Tenant isolation — every account belongs to exactly one business
    business_id = Column(
        Integer, ForeignKey("businesses.id"), nullable=False, index=True
    )

    # Optional link to a Person/Contact
    person_id = Column(
        Integer, ForeignKey("people.id"), nullable=True, index=True
    )

    # Human-readable label — no unique constraint (same name can exist in
    # different businesses; UI warns on apparent duplicate within a business)
    name = Column(String, nullable=False)

    # "person" | "business" | "bank" | "owner"
    account_type = Column(String, nullable=False, default="person")

    # Position type: "tracked" (Money I Track - asset) | "held" (Money Held - liability)
    position_type = Column(String, nullable=False, default="tracked")

    phone = Column(String, nullable=True)
    notes = Column(String, nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    business = relationship("Business", back_populates="tracked_accounts")
    person = relationship(
        "Person",
        back_populates="tracked_accounts",
        overlaps="held_account,tracked_account,tracked_accounts",
    )
    ledger_entries = relationship("LedgerEntry", back_populates="tracked_account")


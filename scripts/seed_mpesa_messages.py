"""Seed the mpesa_messages table with realistic (unused) M-Pesa SMS data.

Each raw_text is written in the exact format the frontend parser
(frontend/lib/features/mpesa/mpesa_sms_parser.dart) accepts, so the messages
also round-trip through the real ingest endpoint (/mpesa/messages POST).

Idempotent: references that already exist for the target business are skipped.

Usage:
    python -m scripts.seed_mpesa_messages [--business-id 1]
"""
import argparse
import datetime as dt
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.database import Base, engine, SessionLocal
from app.models.mpesa_message import MpesaMessage


def _fmt_datetime(value: dt.datetime) -> tuple[str, str]:
    ampm = "AM" if value.hour < 12 else "PM"
    hour = value.hour % 12 or 12
    date = f"{value.day}/{value.month}/{value.year % 100}"
    time = f"{hour}:{value.minute:02d} {ampm}"
    return date, time


def _make_take(ref: str, sender: str, amount: float, at: dt.datetime, balance: float) -> str:
    date, time = _fmt_datetime(at)
    return (
        f"{ref} Confirmed. On {date} at {time} Take Ksh{amount:,.2f} cash from "
        f"{sender}. New M-PESA balance is Ksh{balance:,.2f}. You can now access "
        f"M-PESA via *334#"
    )


def _make_give(ref: str, receiver: str, amount: float, at: dt.datetime, balance: float) -> str:
    date, time = _fmt_datetime(at)
    return (
        f"{ref} Confirmed. On {date} at {time} Give Ksh{amount:,.2f} cash to "
        f"{receiver}. New M-PESA balance is Ksh{balance:,.2f}. You can now access "
        f"M-PESA via *334#"
    )


def _sender_of(raw_text: str) -> str:
    marker = " from " if " Take " in raw_text else " to "
    return raw_text.split(marker, 1)[1].split(". New ", 1)[0].strip()


def _amount_of(raw_text: str) -> float:
    return float(raw_text.split("Ksh")[1].replace(",", "").split()[0])


def seed(business_id: int) -> None:
    eat = ZoneInfo("Africa/Nairobi")
    now = dt.datetime.now(eat)

    def hours_ago(h: float) -> dt.datetime:
        return now - dt.timedelta(hours=h)

    # (reference, kind, counterparty, amount, hours_ago, balance_after)
    specs = [
        # Take: money IN to the float (MONEY_RECEIVED)
        ("KQ8XM7VZ2P", "take", "JOHN KAMAU MOMBASA", 13000.00, 3, 122944.99),
        ("M2L5TN9RW4", "take", "AMINAH HASSAN MOMBASA", 7500.00, 8, 115444.99),
        ("X7QK3RDJ6F", "take", "PETER OCHIENG", 2300.00, 14, 107944.99),
        ("B4W8LSM1ZT", "take", "NAIROBI CASH MERCHANTS LTD", 45000.00, 26, 105644.99),
        ("H5TV9NP2XK", "take", "GRACE WAMBUI KISUMU", 850.00, 31, 60644.99),
        ("V3R8CY7Q2M", "take", "EMMANUEL OTIENO NAKURU", 12400.00, 40, 59794.99),
        ("J6DX4KA9WP", "take", "FAITH NJERI", 1200.00, 47, 47394.99),
        ("Q9NC2H5Y8B", "take", "MOMBASA WHOLESALERS KENYA", 20000.00, 52, 46194.99),
        # Give: money OUT of the float (MONEY_SENT)
        ("T8KX5R9Z3N", "give", "MALSAT TRADERS LTD JOMOKENYATTA AVENUE Mombasa Cbd", 6500.00, 2, 26194.99),
        ("W2F7MH4QD6", "give", "COAST GENERAL SUPPLIERS MOMBASA", 9800.00, 6, 19694.99),
        ("P5RB3NT8YL", "give", "JAMES MWANGI AGENT OUTLET", 3200.00, 12, 9894.99),
        ("C9JX6LK1WG", "give", "SAFARI FRESH PRODUCE LTD", 15500.00, 20, 6694.99),
        ("D4YS7HZ2MV", "give", "AGNES KEMUNTO KISUMU", 4450.00, 28, 22194.99),
        ("G8PL2VX5RC", "give", "TASLAM ENERGY SOLUTIONS LTD", 27000.00, 36, 17744.99),
        ("N3FM6QW8TJ", "give", "BRIAN KIPLAGAT ELDORET", 1850.00, 44, 15244.99),
        ("Z7RT4SD9KA", "give", "KENYA COMMERCIAL SUPPLIERS", 10000.00, 50, 13394.99),
    ]

    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        existing = set(
            db.execute(
                select(MpesaMessage.reference).where(MpesaMessage.business_id == business_id)
            ).scalars()
        )
        added, skipped = 0, 0
        for ref, kind, party, amount, h, balance in specs:
            if ref in existing:
                skipped += 1
                continue
            at = hours_ago(h)
            raw_text = (
                _make_take(ref, party, amount, at, balance)
                if kind == "take"
                else _make_give(ref, party, amount, at, balance)
            )
            db.add(
                MpesaMessage(
                    business_id=business_id,
                    reference=ref,
                    sender=_sender_of(raw_text),
                    amount=amount,
                    direction="MONEY_RECEIVED" if kind == "take" else "MONEY_SENT",
                    raw_text=raw_text,
                    message_timestamp=at.astimezone(dt.timezone.utc),
                    transaction_id=None,
                )
            )
            added += 1
        db.commit()
        print(f"business_id={business_id}: added {added}, skipped {skipped} existing")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-id", type=int, default=1)
    args = parser.parse_args()
    seed(args.business_id)

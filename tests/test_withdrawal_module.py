"""
Tests for the Fpesa Withdrawal V1 module.

Principle: A customer gives you M-Pesa float (+Float credit), and you give
them physical cash (-Cash debit). No sale is recorded.
"""
from datetime import datetime, timezone
import pytest


def _complete_onboarding(client, auth_headers):
    """Helper to complete onboarding so a business exists for the test user."""
    res = client.post(
        "/api/v1/onboarding/complete",
        headers=auth_headers,
        json={
            "business_name": "Test Shop",
            "opening_cash": 10000.0,
            "opening_float": 50000.0,
        },
    )
    assert res.status_code in (200, 201), res.json()


# ---------------------------------------------------------------------------
# Happy-path: ledger effects
# ---------------------------------------------------------------------------

def test_withdrawal_ledger_effects(client, auth_headers):
    """Withdrawal KES 5,000 → Float +5,000 (credit) & Cash -5,000 (debit)."""
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "withdrawal",
            "amount": 5000.0,
            "description": "Customer John Doe withdrawal",
        },
    )
    assert res.status_code in (200, 201), res.json()
    data = res.json()

    assert data["type"] == "withdrawal"
    assert data["amount"] == "5000.00"
    assert data["description"] == "Customer John Doe withdrawal"

    # Multi-leg effects: Float +5000 credit, Cash -5000 debit
    effects = data["effects"]
    assert len(effects) == 2

    float_effect = next(e for e in effects if e["account_type"] == "float")
    cash_effect = next(e for e in effects if e["account_type"] == "cash")

    assert float_effect["direction"] == "credit"
    assert float_effect["amount"] == "5000.00"

    assert cash_effect["direction"] == "debit"
    assert cash_effect["amount"] == "5000.00"


def test_withdrawal_with_sms(client, auth_headers):
    """Withdrawal linking an incoming M-Pesa SMS proof."""
    _complete_onboarding(client, auth_headers)

    # Ingest SMS of 5000
    sms_res = client.post(
        "/api/v1/mpesa/messages",
        headers=auth_headers,
        json={
            "reference": "WDR12345",
            "sender": "John Doe",
            "amount": 5000.0,
            "direction": "MONEY_RECEIVED",
            "raw_text": "Received KSh5,000 from John Doe WDR12345",
            "message_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert sms_res.status_code == 201, sms_res.json()
    sms_id = sms_res.json()["id"]

    # Record withdrawal linking SMS
    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "withdrawal",
            "amount": 5000.0,
            "mpesa_message_id": sms_id,
        },
    )
    assert res.status_code in (200, 201), res.json()
    assert res.json()["mpesa_message_id"] == sms_id


# ---------------------------------------------------------------------------
# Strict validation: amount
# ---------------------------------------------------------------------------

def test_withdrawal_zero_negative_amount_rejected(client, auth_headers):
    """Zero or negative withdrawal amount is rejected with HTTP 422."""
    _complete_onboarding(client, auth_headers)

    res_zero = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "withdrawal", "amount": 0.0},
    )
    assert res_zero.status_code == 422

    res_neg = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "withdrawal", "amount": -500.0},
    )
    assert res_neg.status_code == 422


def test_withdrawal_optional_description(client, auth_headers):
    """Withdrawal with no description should succeed."""
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "withdrawal", "amount": 1000.0},
    )
    assert res.status_code in (200, 201), res.json()

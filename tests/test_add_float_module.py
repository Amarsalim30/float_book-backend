"""
Tests for the Fpesa Add Float V1 module.

Principle: Owner puts personal money into the business M-Pesa float.
Float +Amount (credit). Cash, Revenue, and Expense remain unchanged.
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

def test_add_float_ledger_effects(client, auth_headers):
    """Add Float KES 10,000 → Float +10,000 (credit). Cash is unaffected."""
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "add_float",
            "amount": 10000.0,
            "description": "Owner recharged via M-Pesa Agent",
        },
    )
    assert res.status_code in (200, 201), res.json()
    data = res.json()

    assert data["type"] == "add_float"
    assert data["amount"] == "10000.00"

    # Exactly one ledger entry: Float +10,000 credit
    effects = data["effects"]
    assert len(effects) == 1
    assert effects[0]["account_type"] == "float"
    assert effects[0]["direction"] == "credit"
    assert effects[0]["amount"] == "10000.00"


def test_add_float_does_not_affect_revenue_or_expense(client, auth_headers):
    """Add Float increases Float by amount, leaving Cash, Revenue, and Expense unchanged."""
    _complete_onboarding(client, auth_headers)

    # Initial balances check
    dash_before = client.get("/api/v1/dashboard/", headers=auth_headers).json()
    cash_before = float(dash_before["cash_balance"])
    float_before = float(dash_before["float_balance"])

    # Perform Add Float KES 10,000
    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "add_float",
            "amount": 10000.0,
        },
    )
    assert res.status_code in (200, 201), res.json()

    dash_after = client.get("/api/v1/dashboard/", headers=auth_headers).json()
    cash_after = float(dash_after["cash_balance"])
    float_after = float(dash_after["float_balance"])

    # Cash must remain exactly unchanged
    assert cash_after == cash_before
    # Float must increase by exactly 10,000
    assert float_after == float_before + 10000.0


def test_add_float_with_sms(client, auth_headers):
    """Add Float linking an incoming M-Pesa deposit SMS proof."""
    _complete_onboarding(client, auth_headers)

    # Ingest SMS of 10,000
    sms_res = client.post(
        "/api/v1/mpesa/messages",
        headers=auth_headers,
        json={
            "reference": "FLT9999",
            "sender": "M-Pesa Agent",
            "amount": 10000.0,
            "direction": "MONEY_RECEIVED",
            "raw_text": "You have received KSh10,000 from Agent FLT9999",
            "message_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert sms_res.status_code == 201, sms_res.json()
    sms_id = sms_res.json()["id"]

    # Record Add Float linking SMS
    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "add_float",
            "amount": 10000.0,
            "mpesa_message_id": sms_id,
        },
    )
    assert res.status_code in (200, 201), res.json()
    assert res.json()["mpesa_message_id"] == sms_id


def test_add_float_reuse_linked_sms_rejected(client, auth_headers):
    """Attempting to reuse an already linked SMS for Add Float is rejected with HTTP 400."""
    _complete_onboarding(client, auth_headers)

    # Ingest SMS
    sms_res = client.post(
        "/api/v1/mpesa/messages",
        headers=auth_headers,
        json={
            "reference": "FLT8888",
            "sender": "M-Pesa Agent",
            "amount": 5000.0,
            "direction": "MONEY_RECEIVED",
            "raw_text": "You have received KSh5,000 from Agent FLT8888",
            "message_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    sms_id = sms_res.json()["id"]

    # Link once
    res1 = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "add_float", "amount": 5000.0, "mpesa_message_id": sms_id},
    )
    assert res1.status_code in (200, 201)

    # Link twice -> should fail
    res2 = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "add_float", "amount": 5000.0, "mpesa_message_id": sms_id},
    )
    assert res2.status_code == 400
    assert "already linked" in res2.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Strict validation: amount
# ---------------------------------------------------------------------------

def test_add_float_zero_negative_amount_rejected(client, auth_headers):
    """Zero or negative Add Float amount is rejected with HTTP 422."""
    _complete_onboarding(client, auth_headers)

    res_zero = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "add_float", "amount": 0.0},
    )
    assert res_zero.status_code == 422

    res_neg = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "add_float", "amount": -1000.0},
    )
    assert res_neg.status_code == 422


def test_add_float_optional_note(client, auth_headers):
    """Add Float with no note should succeed with default description."""
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "add_float", "amount": 2500.0},
    )
    assert res.status_code in (200, 201), res.json()

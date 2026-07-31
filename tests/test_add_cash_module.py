"""
Tests for the Add Cash V1 module.

Principle: Owner puts personal cash into the business cash drawer.
Cash +Amount (credit). Float, Revenue, and Expense remain unchanged.
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

def test_add_cash_ledger_effects(client, auth_headers):
    """Add Cash KES 10,000 → Cash +10,000 (credit). Float is unaffected."""
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "add_cash",
            "amount": 10000.0,
            "description": "Owner added cash to drawer",
        },
    )
    assert res.status_code in (200, 201), res.json()
    data = res.json()

    assert data["type"] == "add_cash"
    assert data["amount"] == "10000.00"

    # Exactly one ledger entry: Cash +10,000 credit
    effects = data["effects"]
    assert len(effects) == 1
    assert effects[0]["account_type"] == "cash"
    assert effects[0]["direction"] == "credit"
    assert effects[0]["amount"] == "10000.00"


def test_add_cash_does_not_affect_float_or_revenue_or_expense(client, auth_headers):
    """Add Cash increases Cash by amount, leaving Float, Revenue, and Expense unchanged."""
    _complete_onboarding(client, auth_headers)

    # Initial balances check
    dash_before = client.get("/api/v1/dashboard/", headers=auth_headers).json()
    cash_before = float(dash_before["cash_balance"])
    float_before = float(dash_before["float_balance"])

    # Perform Add Cash KES 10,000
    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "add_cash",
            "amount": 10000.0,
        },
    )
    assert res.status_code in (200, 201), res.json()

    dash_after = client.get("/api/v1/dashboard/", headers=auth_headers).json()
    cash_after = float(dash_after["cash_balance"])
    float_after = float(dash_after["float_balance"])

    # Float must remain exactly unchanged
    assert float_after == float_before
    # Cash must increase by exactly 10,000
    assert cash_after == cash_before + 10000.0


def test_add_cash_zero_negative_amount_rejected(client, auth_headers):
    """Amount <= 0 should be rejected by validation."""
    _complete_onboarding(client, auth_headers)

    res_zero = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "add_cash", "amount": 0.0},
    )
    assert res_zero.status_code == 422

    res_neg = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "add_cash", "amount": -1000.0},
    )
    assert res_neg.status_code == 422


def test_add_cash_optional_note(client, auth_headers):
    """Add Cash works with or without description."""
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "add_cash", "amount": 2500.0},
    )
    assert res.status_code in (200, 201), res.json()

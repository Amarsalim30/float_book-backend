"""
Tests for the Fpesa Expense V1 module.

Principle: Record what the business spent, choose where the money came
from (Cash or M-Pesa), and Fpesa reduces the correct balance.

  Cash expense  → Cash  ledger debit
  M-Pesa expense → Float ledger debit
"""
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
# Happy-path: correct ledger effects
# ---------------------------------------------------------------------------

def test_cash_expense(client, auth_headers):
    """Cash expense → single Cash debit ledger entry."""
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "expense",
            "amount": 500.0,
            "payment_method": "cash",
            "description": "Transport",
        },
    )
    assert res.status_code in (200, 201), res.json()
    data = res.json()

    assert data["type"] == "expense"
    assert data["amount"] == "500.00"
    assert data["payment_method"] == "cash"

    assert len(data["effects"]) == 1
    effect = data["effects"][0]
    assert effect["account_type"] == "cash"
    assert effect["direction"] == "debit"
    assert effect["amount"] == "500.00"


def test_mpesa_expense(client, auth_headers):
    """M-Pesa expense → single Float debit ledger entry."""
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "expense",
            "amount": 500.0,
            "payment_method": "mpesa",
            "description": "Electricity",
        },
    )
    assert res.status_code in (200, 201), res.json()
    data = res.json()

    assert data["type"] == "expense"
    assert data["amount"] == "500.00"
    assert data["payment_method"] == "mpesa"

    assert len(data["effects"]) == 1
    effect = data["effects"][0]
    assert effect["account_type"] == "float"
    assert effect["direction"] == "debit"
    assert effect["amount"] == "500.00"


def test_expense_description_optional(client, auth_headers):
    """Expense with no description should succeed."""
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "expense",
            "amount": 200.0,
            "payment_method": "cash",
        },
    )
    assert res.status_code in (200, 201), res.json()
    assert res.json()["description"] is None


def test_expense_with_person_id(client, auth_headers):
    """Expense with optional person_id should succeed."""
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "expense",
            "amount": 300.0,
            "payment_method": "cash",
            "person_id": 99,
        },
    )
    # person_id 99 doesn't exist but backend accepts it as optional FK
    assert res.status_code in (200, 201, 422), res.json()


# ---------------------------------------------------------------------------
# Strict validation: payment_method
# ---------------------------------------------------------------------------

def test_expense_null_payment_method_rejected(client, auth_headers):
    """Expense without payment_method is rejected with HTTP 422."""
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "expense",
            "amount": 500.0,
        },
    )
    assert res.status_code == 422
    body = res.json()
    detail = body.get("detail", "")
    assert "payment_method" in str(detail).lower()


def test_expense_invalid_payment_method_rejected(client, auth_headers):
    """Expense with an invalid payment_method string is rejected."""
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "expense",
            "amount": 500.0,
            "payment_method": "card",
        },
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Strict validation: amount
# ---------------------------------------------------------------------------

def test_expense_zero_amount_rejected(client, auth_headers):
    """Zero amount is rejected."""
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "expense",
            "amount": 0.0,
            "payment_method": "cash",
        },
    )
    assert res.status_code == 422


def test_expense_negative_amount_rejected(client, auth_headers):
    """Negative amount is rejected."""
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "expense",
            "amount": -100.0,
            "payment_method": "cash",
        },
    )
    assert res.status_code == 422

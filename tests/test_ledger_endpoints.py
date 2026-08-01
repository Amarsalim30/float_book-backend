"""
Tests for Ledger statement endpoints (/api/v1/ledger/{account_type}) and transaction search/detail endpoints.
"""
from decimal import Decimal
import pytest


def test_ledger_cash_and_float_statements(client, auth_headers):
    # 1. Complete onboarding with initial cash & float seed balances
    onboarding_res = client.post(
        "/api/v1/onboarding/complete",
        json={
            "business_name": "Test Agent Shop",
            "opening_cash": 10000.00,
            "opening_float": 50000.00,
        },
        headers=auth_headers,
    )
    assert onboarding_res.status_code == 201

    # 2. Record cash sale (+2000 cash)
    sale_res = client.post(
        "/api/v1/transactions/",
        json={
            "type": "sale",
            "amount": "2000.00",
            "payment_method": "cash",
            "description": "Cash sale of airtime",
        },
        headers=auth_headers,
    )
    assert sale_res.status_code == 201

    # 3. Record expense (-500 cash)
    expense_res = client.post(
        "/api/v1/transactions/",
        json={
            "type": "expense",
            "amount": "500.00",
            "payment_method": "cash",
            "description": "Lunch expense",
        },
        headers=auth_headers,
    )
    assert expense_res.status_code == 201

    # 4. Fetch GET /api/v1/ledger/cash
    cash_ledger = client.get("/api/v1/ledger/cash", headers=auth_headers)
    assert cash_ledger.status_code == 200
    cash_data = cash_ledger.json()

    assert cash_data["account_type"] == "cash"
    assert Decimal(str(cash_data["current_balance"])) == Decimal("11500.00")
    assert cash_data["total"] == 3
    # Check items are newest first
    items = cash_data["items"]
    assert items[0]["description"] == "Lunch expense"
    assert Decimal(str(items[0]["running_balance"])) == Decimal("11500.00")
    assert items[1]["description"] == "Cash sale of airtime"
    assert Decimal(str(items[1]["running_balance"])) == Decimal("12000.00")
    assert items[2]["description"] == "Opening cash balance"
    assert Decimal(str(items[2]["running_balance"])) == Decimal("10000.00")

    # 5. Fetch GET /api/v1/ledger/float
    float_ledger = client.get("/api/v1/ledger/float", headers=auth_headers)
    assert float_ledger.status_code == 200
    float_data = float_ledger.json()

    assert float_data["account_type"] == "float"
    assert Decimal(str(float_data["current_balance"])) == Decimal("50000.00")
    assert float_data["total"] == 1


def test_transaction_search_and_detail(client, auth_headers):
    # Setup onboarding
    client.post(
        "/api/v1/onboarding/complete",
        json={
            "business_name": "Search Test Shop",
            "opening_cash": 5000.00,
            "opening_float": 5000.00,
        },
        headers=auth_headers,
    )

    # Create transaction with unique reference
    tx_res = client.post(
        "/api/v1/transactions/",
        json={
            "type": "sale",
            "amount": "1500.00",
            "payment_method": "cash",
            "reference": "REF999X",
            "description": "Special Cement Bag",
        },
        headers=auth_headers,
    )
    assert tx_res.status_code == 201
    tx_id = tx_res.json()["id"]

    # Search by q=REF999X
    search_res = client.get("/api/v1/transactions/?q=REF999X", headers=auth_headers)
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total"] == 1
    assert search_data["items"][0]["id"] == tx_id

    # Fetch detail GET /api/v1/transactions/{id}
    detail_res = client.get(f"/api/v1/transactions/{tx_id}", headers=auth_headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["reference"] == "REF999X"

from decimal import Decimal
import pytest


def test_today_reconciliation_calculations(client, auth_headers):
    # 1. Onboarding
    onboarding_res = client.post(
        "/api/v1/onboarding/complete",
        json={
            "business_name": "Reconciliation Test Shop",
            "opening_cash": 10000.00,
            "opening_float": 50000.00,
        },
        headers=auth_headers,
    )
    assert onboarding_res.status_code == 201

    # 2. Add cash sale (+2000 cash)
    client.post(
        "/api/v1/transactions/",
        json={
            "type": "sale",
            "amount": "2000.00",
            "payment_method": "cash",
            "description": "Morning soda sale",
        },
        headers=auth_headers,
    )

    # 3. Add expense (-500 cash)
    client.post(
        "/api/v1/transactions/",
        json={
            "type": "expense",
            "amount": "500.00",
            "payment_method": "cash",
            "description": "Lunch",
        },
        headers=auth_headers,
    )

    # 4. Check today reconciliation
    recon_res = client.get("/api/v1/close-day/today", headers=auth_headers)
    assert recon_res.status_code == 200
    data = recon_res.json()

    assert data["is_already_closed"] is False
    assert Decimal(str(data["expected_cash"])) == Decimal("11500.00")
    assert Decimal(str(data["expected_float"])) == Decimal("50000.00")
    assert len(data["today_transactions"]) >= 2


def test_close_day_balanced(client, auth_headers):
    # Complete onboarding
    client.post(
        "/api/v1/onboarding/complete",
        json={
            "business_name": "Balanced Shop",
            "opening_cash": 5000.00,
            "opening_float": 20000.00,
        },
        headers=auth_headers,
    )

    # Close day with exact counts
    close_res = client.post(
        "/api/v1/close-day",
        json={
            "actual_cash": "5000.00",
            "actual_float": "20000.00",
            "notes": "All matched perfectly",
            "post_adjustment": False,
        },
        headers=auth_headers,
    )
    assert close_res.status_code == 201
    data = close_res.json()

    assert data["status"] == "balanced"
    assert Decimal(str(data["cash_variance"])) == Decimal("0.00")
    assert Decimal(str(data["float_variance"])) == Decimal("0.00")

    # Verify dashboard reflects closed day
    dash_res = client.get("/api/v1/dashboard/", headers=auth_headers)
    assert dash_res.status_code == 200
    assert dash_res.json()["day_closed"] is True
    assert Decimal(str(dash_res.json()["closing_variance"])) == Decimal("0.00")


def test_close_day_with_discrepancy_and_notes(client, auth_headers):
    # Complete onboarding
    client.post(
        "/api/v1/onboarding/complete",
        json={
            "business_name": "Discrepancy Shop",
            "opening_cash": 10000.00,
            "opening_float": 30000.00,
        },
        headers=auth_headers,
    )

    # Actual cash is 9800 (deficit 200), Float is 30100 (surplus 100)
    close_res = client.post(
        "/api/v1/close-day",
        json={
            "actual_cash": "9800.00",
            "actual_float": "30100.00",
            "notes": "Cash drawer shortage 200, float tips 100",
            "post_adjustment": False,
        },
        headers=auth_headers,
    )
    assert close_res.status_code == 201
    data = close_res.json()

    assert data["status"] == "discrepancy"
    assert Decimal(str(data["cash_variance"])) == Decimal("-200.00")
    assert Decimal(str(data["float_variance"])) == Decimal("100.00")

    # Check History
    hist_res = client.get("/api/v1/close-day/history", headers=auth_headers)
    assert hist_res.status_code == 200
    hdata = hist_res.json()
    assert hdata["stats"]["total_closed_days"] == 1
    assert hdata["stats"]["discrepancy_days"] == 1
    assert hdata["stats"]["balanced_days"] == 0


def test_close_day_with_adjustment_posting(client, auth_headers):
    # Complete onboarding
    client.post(
        "/api/v1/onboarding/complete",
        json={
            "business_name": "Adjustment Shop",
            "opening_cash": 10000.00,
            "opening_float": 30000.00,
        },
        headers=auth_headers,
    )

    # Expected is 10000 cash, actual is 9500 (short 500)
    close_res = client.post(
        "/api/v1/close-day",
        json={
            "actual_cash": "9500.00",
            "actual_float": "30000.00",
            "notes": "Lost 500 note, post adjustment",
            "post_adjustment": True,
        },
        headers=auth_headers,
    )
    assert close_res.status_code == 201
    data = close_res.json()
    assert data["post_adjustment"] is True
    assert data["adjustment_transaction_id"] is not None

    # After adjustment, ledger current balance must equal actual count 9500.00
    dash_res = client.get("/api/v1/dashboard/", headers=auth_headers)
    assert dash_res.status_code == 200
    assert Decimal(str(dash_res.json()["cash_balance"])) == Decimal("9500.00")

    # Resubmit close day: actual count is corrected to 9800.00 (short 200 instead of 500)
    resubmit_res = client.post(
        "/api/v1/close-day",
        json={
            "actual_cash": "9800.00",
            "actual_float": "30000.00",
            "notes": "Found 300 in till, updated shortage 200",
            "post_adjustment": True,
        },
        headers=auth_headers,
    )
    assert resubmit_res.status_code == 201
    resubmit_data = resubmit_res.json()
    assert Decimal(str(resubmit_data["cash_variance"])) == Decimal("-200.00")

    # Balance must reflect the updated count (9800), not double adjusted
    dash_res_updated = client.get("/api/v1/dashboard/", headers=auth_headers)
    assert dash_res_updated.status_code == 200
    assert Decimal(str(dash_res_updated.json()["cash_balance"])) == Decimal("9800.00")


def test_dashboard_detects_offsetting_discrepancy(client, auth_headers):
    # Complete onboarding
    client.post(
        "/api/v1/onboarding/complete",
        json={
            "business_name": "Offsetting Shop",
            "opening_cash": 10000.00,
            "opening_float": 30000.00,
        },
        headers=auth_headers,
    )

    # Cash is short 500 (9500), Float is over 500 (30500)
    # Net variance sum is 0, but status is discrepancy
    close_res = client.post(
        "/api/v1/close-day",
        json={
            "actual_cash": "9500.00",
            "actual_float": "30500.00",
            "notes": "Drawer swap between cash and float",
            "post_adjustment": False,
        },
        headers=auth_headers,
    )
    assert close_res.status_code == 201

    dash_res = client.get("/api/v1/dashboard/", headers=auth_headers)
    assert dash_res.status_code == 200
    data = dash_res.json()
    assert data["day_closed"] is True
    assert data["day_status"] == "discrepancy"
    assert Decimal(str(data["closing_cash_variance"])) == Decimal("-500.00")
    assert Decimal(str(data["closing_float_variance"])) == Decimal("500.00")


"""
Tests for date_from and date_to parameters on GET /api/v1/transactions/
"""
from datetime import datetime, timedelta, timezone


def _complete_onboarding(client, auth_headers):
    res = client.post(
        "/api/v1/onboarding/complete",
        headers=auth_headers,
        json={
            "business_name": "Filter Shop",
            "opening_cash": 1000.0,
            "opening_float": 5000.0,
        },
    )
    assert res.status_code in (200, 201), res.json()


def test_transactions_date_filtering(client, auth_headers):
    _complete_onboarding(client, auth_headers)

    # Create a transaction today
    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 500.0,
            "payment_method": "cash",
            "description": "Sale 1",
        },
    )
    assert res.status_code == 201
    tx = res.json()

    now_utc = datetime.now(timezone.utc)
    start_today = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    end_today = now_utc.replace(hour=23, minute=59, second=59, microsecond=999999)

    start_iso = start_today.isoformat().replace("+00:00", "Z")
    end_iso = end_today.isoformat().replace("+00:00", "Z")

    # Filter by Today's date range
    res_today = client.get(
        f"/api/v1/transactions/?date_from={start_iso}&date_to={end_iso}",
        headers=auth_headers,
    )
    assert res_today.status_code == 200
    data_today = res_today.json()
    assert data_today["total"] >= 1
    assert any(item["id"] == tx["id"] for item in data_today["items"])

    # Filter by future date range (should return 0)
    future_start = (now_utc + timedelta(days=10)).isoformat().replace("+00:00", "Z")
    future_end = (now_utc + timedelta(days=11)).isoformat().replace("+00:00", "Z")
    res_future = client.get(
        f"/api/v1/transactions/?date_from={future_start}&date_to={future_end}",
        headers=auth_headers,
    )
    assert res_future.status_code == 200
    assert res_future.json()["total"] == 0

import pytest

def test_complete_onboarding(client, auth_headers):
    response = client.post(
        "/api/v1/onboarding/complete",
        json={
            "business_name": "Test M-Pesa Shop",
            "opening_cash": 50000.0,
            "opening_float": 20000.0,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.json()


def test_dashboard_unrecorded_mpesa(client, auth_headers):
    # Complete onboarding
    client.post(
        "/api/v1/onboarding/complete",
        json={
            "business_name": "Test M-Pesa Shop",
            "opening_cash": 50000.0,
            "opening_float": 20000.0,
        },
        headers=auth_headers,
    )

    # Ingest an M-Pesa message
    msg_res = client.post(
        "/api/v1/mpesa/messages",
        json={
            "reference": "TESTDASH01",
            "sender": "JOHN DOE",
            "amount": 2500.00,
            "direction": "MONEY_RECEIVED",
            "raw_text": "TESTDASH01 Confirmed. Give Ksh2,500.00 to JOHN DOE...",
            "message_timestamp": "2026-10-09T10:00:00Z",
        },
        headers=auth_headers,
    )
    assert msg_res.status_code == 201

    # Check dashboard reflects the unrecorded message
    dash_res = client.get("/api/v1/dashboard", headers=auth_headers)
    assert dash_res.status_code == 200
    data = dash_res.json()
    assert data["unrecorded_mpesa_count"] == 1
    assert float(data["unrecorded_mpesa_total"]) == 2500.00

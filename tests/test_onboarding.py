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

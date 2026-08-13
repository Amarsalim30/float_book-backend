from datetime import datetime, timezone
import pytest
from sqlalchemy.exc import IntegrityError
from app.models.mpesa_message import MpesaMessage


def _complete_onboarding(client, auth_headers):
    res = client.post(
        "/api/v1/onboarding/complete",
        headers=auth_headers,
        json={
            "business_name": "Dedupe Shop",
            "opening_cash": 10000.0,
            "opening_float": 50000.0,
        },
    )
    assert res.status_code in (200, 201), res.json()


def test_duplicate_sms_ingestion_returns_existing_record(client, auth_headers):
    """Ingesting an SMS with an existing reference returns the existing record without duplicating."""
    _complete_onboarding(client, auth_headers)

    payload = {
        "reference": "REF_DEDUPE_001",
        "sender": "Customer Duplicate",
        "amount": 2500.0,
        "direction": "MONEY_RECEIVED",
        "raw_text": "Received 2,500 KES from Customer Duplicate REF_DEDUPE_001",
        "message_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # First ingestion
    res1 = client.post("/api/v1/mpesa/messages", headers=auth_headers, json=payload)
    assert res1.status_code == 201, res1.json()
    msg1 = res1.json()

    # Second ingestion (duplicate payload)
    res2 = client.post("/api/v1/mpesa/messages", headers=auth_headers, json=payload)
    assert res2.status_code in (200, 201), res2.json()
    msg2 = res2.json()

    # Both responses should return the exact same SMS ID
    assert msg1["id"] == msg2["id"]
    assert msg1["reference"] == msg2["reference"]

    # Verify only ONE message exists in the database
    get_res = client.get(
        "/api/v1/mpesa/messages?direction=MONEY_RECEIVED&unused=true",
        headers=auth_headers,
    )
    assert get_res.status_code == 200
    matching = [m for m in get_res.json() if m["reference"] == "REF_DEDUPE_001"]
    assert len(matching) == 1


def test_different_businesses_can_have_same_reference(client, auth_headers):
    """Two different businesses can ingest messages with the same reference without conflict."""
    _complete_onboarding(client, auth_headers)

    # Register and onboard second business
    user_b = client.post(
        "/api/v1/auth/register",
        json={"email": "biz_b@example.com", "password": "Password123", "full_name": "Biz B"},
    ).json()
    token_b = client.post(
        "/api/v1/auth/login",
        json={"email": "biz_b@example.com", "password": "Password123"},
    ).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    res_b = client.post(
        "/api/v1/onboarding/complete",
        headers=headers_b,
        json={"business_name": "Shop B", "opening_cash": 1000.0, "opening_float": 1000.0},
    )
    assert res_b.status_code in (200, 201)

    payload = {
        "reference": "SHARED_REF_999",
        "sender": "Common Sender",
        "amount": 1000.0,
        "direction": "MONEY_RECEIVED",
        "raw_text": "Received 1,000 KES SHARED_REF_999",
        "message_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Ingest for Business A
    res1 = client.post("/api/v1/mpesa/messages", headers=auth_headers, json=payload)
    assert res1.status_code == 201

    # Ingest for Business B
    res2 = client.post("/api/v1/mpesa/messages", headers=headers_b, json=payload)
    assert res2.status_code == 201

    # Unique records created for each business
    assert res1.json()["id"] != res2.json()["id"]
    assert res1.json()["reference"] == res2.json()["reference"] == "SHARED_REF_999"

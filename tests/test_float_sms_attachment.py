from datetime import datetime, timezone


def _complete_onboarding(client, auth_headers):
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


def _ingest(client, auth_headers, reference, direction, amount=5000.0, sender="Customer X"):
    res = client.post(
        "/api/v1/mpesa/messages",
        headers=auth_headers,
        json={
            "reference": reference,
            "sender": sender,
            "amount": amount,
            "direction": direction,
            "raw_text": f"raw {direction} {amount}",
            "message_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert res.status_code == 201, res.json()
    return res.json()["id"]


def test_unused_messages_list_by_direction(client, auth_headers):
    _complete_onboarding(client, auth_headers)
    _ingest(client, auth_headers, "TAKE123", "MONEY_RECEIVED")
    give_id = _ingest(client, auth_headers, "GIVE456", "MONEY_SENT")

    res = client.get("/api/v1/mpesa/messages?direction=MONEY_SENT&unused=true", headers=auth_headers)
    assert res.status_code == 200
    ids = [m["id"] for m in res.json()]
    assert give_id in ids
    assert all(m["direction"] == "MONEY_SENT" for m in res.json())

    res = client.get("/api/v1/mpesa/messages?direction=MONEY_RECEIVED&unused=true", headers=auth_headers)
    assert res.status_code == 200
    assert all(m["direction"] == "MONEY_RECEIVED" for m in res.json())


def test_withdrawal_requires_give_sms(client, auth_headers):
    _complete_onboarding(client, auth_headers)
    give_id = _ingest(client, auth_headers, "GIVE456", "MONEY_SENT")
    take_id = _ingest(client, auth_headers, "TAKE789", "MONEY_RECEIVED")

    # Give (MONEY_SENT) is accepted for a withdrawal.
    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "withdrawal", "amount": 5000.0, "mpesa_message_id": give_id},
    )
    assert res.status_code in (200, 201), res.json()
    assert res.json()["mpesa_message_id"] == give_id

    # Take (MONEY_RECEIVED) is rejected for a withdrawal.
    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "withdrawal", "amount": 5000.0, "mpesa_message_id": take_id},
    )
    assert res.status_code == 400, res.json()
    assert "MONEY_SENT" in res.json()["detail"]


def test_add_float_requires_take_sms(client, auth_headers):
    _complete_onboarding(client, auth_headers)
    give_id = _ingest(client, auth_headers, "GIVE456", "MONEY_SENT")
    take_id = _ingest(client, auth_headers, "TAKE789", "MONEY_RECEIVED")

    # Take (MONEY_RECEIVED) is accepted for an add_float deposit.
    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "add_float", "amount": 5000.0, "mpesa_message_id": take_id},
    )
    assert res.status_code in (200, 201), res.json()
    assert res.json()["mpesa_message_id"] == take_id

    # Give (MONEY_SENT) is rejected for an add_float deposit.
    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "add_float", "amount": 5000.0, "mpesa_message_id": give_id},
    )
    assert res.status_code == 400, res.json()
    assert "MONEY_RECEIVED" in res.json()["detail"]

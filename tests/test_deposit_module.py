from datetime import datetime, timezone


def _complete_onboarding(client, auth_headers):
    res = client.post(
        "/api/v1/onboarding/complete",
        headers=auth_headers,
        json={
            "business_name": "Deposit Shop",
            "opening_cash": 10000.0,
            "opening_float": 50000.0,
        },
    )
    assert res.status_code in (200, 201), res.json()


def _ingest_sms(client, auth_headers, reference="GIVE999", direction="MONEY_SENT", amount=3000.0):
    res = client.post(
        "/api/v1/mpesa/messages",
        headers=auth_headers,
        json={
            "reference": reference,
            "sender": "0712345678",
            "amount": amount,
            "direction": direction,
            "raw_text": f"Sent {amount} KES to customer",
            "message_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert res.status_code == 201, res.json()
    return res.json()["id"]


def test_record_deposit_increases_cash_decreases_float(client, auth_headers):
    """Deposit of 5,000 KES adds 5,000 to Cash and subtracts 5,000 from Float."""
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "deposit",
            "amount": 5000.0,
            "description": "Customer cash deposit",
        },
    )
    assert res.status_code in (200, 201), res.json()
    data = res.json()
    assert data["type"] == "deposit"
    assert float(data["amount"]) == 5000.0

    # Verify Dashboard KPIs
    dash = client.get("/api/v1/dashboard/", headers=auth_headers).json()
    # Opening Cash 10,000 + 5,000 Deposit = 15,000 Cash
    # Opening Float 50,000 - 5,000 Deposit = 45,000 Float
    assert float(dash["cash_balance"]) == 15000.0
    assert float(dash["float_balance"]) == 45000.0


def test_deposit_links_give_sms_proof(client, auth_headers):
    """Deposit links an M-Pesa Give (MONEY_SENT) SMS proof correctly."""
    _complete_onboarding(client, auth_headers)
    sms_id = _ingest_sms(client, auth_headers, reference="GIVE_DEP_1", direction="MONEY_SENT", amount=3000.0)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "deposit",
            "amount": 3000.0,
            "mpesa_message_id": sms_id,
            "description": "Deposit backed by Give SMS",
        },
    )
    assert res.status_code in (200, 201), res.json()
    assert res.json()["mpesa_message_id"] == sms_id

    # Linked SMS no longer shows up as unused
    unused = client.get(
        "/api/v1/mpesa/messages?direction=MONEY_SENT&unused=true",
        headers=auth_headers,
    ).json()
    assert all(m["id"] != sms_id for m in unused)


def test_deposit_rejects_negative_or_zero_amount(client, auth_headers):
    """Deposit rejects amounts <= 0 with HTTP 422."""
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "deposit", "amount": 0.0},
    )
    assert res.status_code == 422

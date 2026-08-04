from decimal import Decimal


def _complete_onboarding(client, auth_headers):
    """Helper to complete onboarding so business exists for user."""
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


def _create_sale(client, auth_headers, amount=600.0):
    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": amount,
            "payment_method": "cash",
            "description": "Original sale",
        },
    )
    assert res.status_code in (200, 201), res.json()
    return res.json()


def _cash_balance(client, auth_headers):
    res = client.get("/api/v1/ledger/cash", headers=auth_headers)
    assert res.status_code == 200, res.json()
    return Decimal(res.json()["current_balance"])


def test_update_changes_amount_and_effects(client, auth_headers):
    _complete_onboarding(client, auth_headers)
    tx = _create_sale(client, auth_headers, amount=600.0)
    tx_id = tx["id"]

    res = client.put(
        f"/api/v1/transactions/{tx_id}",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 1000.0,
            "payment_method": "cash",
            "description": "Edited sale",
        },
    )
    assert res.status_code == 200, res.json()
    data = res.json()
    assert data["id"] == tx_id
    assert data["amount"] == "1000.00"
    assert data["description"] == "Edited sale"
    assert len(data["effects"]) == 1
    assert data["effects"][0]["amount"] == "1000.00"
    # Old +600 credit was replaced by +1000, so cash balance grows by 1000 only.
    assert _cash_balance(client, auth_headers) == Decimal("11000.00")


def test_update_type_swaps_ledger_effects(client, auth_headers):
    _complete_onboarding(client, auth_headers)
    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "withdrawal", "amount": 500.0},
    )
    assert res.status_code in (200, 201), res.json()
    tx_id = res.json()["id"]

    res = client.put(
        f"/api/v1/transactions/{tx_id}",
        headers=auth_headers,
        json={"type": "add_cash", "amount": 500.0},
    )
    assert res.status_code == 200, res.json()
    data = res.json()
    assert data["type"] == "add_cash"
    assert data["payment_method"] is None
    assert len(data["effects"]) == 1
    assert data["effects"][0]["account_type"] == "cash"
    assert data["effects"][0]["direction"] == "credit"
    # Withdrawal (float +500 / cash -500) is fully reversed; add_cash is cash +500.
    assert _cash_balance(client, auth_headers) == Decimal("10500.00")


def test_update_invalid_type_rejected(client, auth_headers):
    _complete_onboarding(client, auth_headers)
    tx = _create_sale(client, auth_headers)
    res = client.put(
        f"/api/v1/transactions/{tx['id']}",
        headers=auth_headers,
        json={"type": "transfer", "amount": 100.0},
    )
    assert res.status_code == 422, res.json()


def test_delete_reverses_balance(client, auth_headers):
    _complete_onboarding(client, auth_headers)
    tx = _create_sale(client, auth_headers, amount=600.0)
    tx_id = tx["id"]
    assert _cash_balance(client, auth_headers) == Decimal("10600.00")

    res = client.delete(f"/api/v1/transactions/{tx_id}", headers=auth_headers)
    assert res.status_code == 204, res.json()

    # Transaction and its ledger effects are gone; balance back to opening.
    assert _cash_balance(client, auth_headers) == Decimal("10000.00")
    res = client.get(f"/api/v1/transactions/{tx_id}", headers=auth_headers)
    assert res.status_code == 404


def test_delete_missing_transaction_returns_404(client, auth_headers):
    _complete_onboarding(client, auth_headers)
    res = client.delete("/api/v1/transactions/999999", headers=auth_headers)
    assert res.status_code == 404, res.json()


def _ingest_mpesa_sms(client, auth_headers, amount=600.0):
    from datetime import datetime, timezone

    sms_res = client.post(
        "/api/v1/mpesa/messages",
        headers=auth_headers,
        json={
            "reference": "ABC123",
            "sender": "Customer X",
            "amount": amount,
            "direction": "MONEY_RECEIVED",
            "raw_text": "Received KSh600 from Customer X ABC123",
            "message_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert sms_res.status_code == 201, sms_res.json()
    return sms_res.json()["id"]


def _float_balance(client, auth_headers):
    res = client.get("/api/v1/ledger/float", headers=auth_headers)
    assert res.status_code == 200, res.json()
    return Decimal(res.json()["current_balance"])


def test_update_mpesa_sale_keeps_sms_and_recomputes_change(client, auth_headers):
    _complete_onboarding(client, auth_headers)
    sms_id = _ingest_mpesa_sms(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 600.0,
            "payment_method": "mpesa",
            "mpesa_message_id": sms_id,
        },
    )
    assert res.status_code in (200, 201), res.json()
    tx_id = res.json()["id"]
    assert _float_balance(client, auth_headers) == Decimal("50600.00")

    # Edit: same SMS proof, but customer paid 1000 so change is given from cash.
    res = client.put(
        f"/api/v1/transactions/{tx_id}",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 600.0,
            "amount_received": 1000.0,
            "payment_method": "mpesa",
            "mpesa_message_id": sms_id,
        },
    )
    assert res.status_code == 200, res.json()
    data = res.json()
    assert data["mpesa_message_id"] == sms_id
    assert data["amount_received"] == "1000.00"
    assert data["change_amount"] == "400.00"
    assert len(data["effects"]) == 2
    # Float +1000, cash -400
    assert _float_balance(client, auth_headers) == Decimal("51000.00")
    assert _cash_balance(client, auth_headers) == Decimal("9600.00")


def test_update_mpesa_sale_removing_sms_unlinks_and_freees_it(client, auth_headers):
    _complete_onboarding(client, auth_headers)
    sms_id = _ingest_mpesa_sms(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 600.0,
            "payment_method": "mpesa",
            "mpesa_message_id": sms_id,
        },
    )
    assert res.status_code in (200, 201), res.json()
    tx_id = res.json()["id"]

    res = client.put(
        f"/api/v1/transactions/{tx_id}",
        headers=auth_headers,
        json={"type": "sale", "amount": 600.0, "payment_method": "mpesa", "mpesa_message_id": None},
    )
    assert res.status_code == 200, res.json()
    assert res.json()["mpesa_message_id"] is None

    list_res = client.get(
        "/api/v1/mpesa/messages?direction=MONEY_RECEIVED&unused=true", headers=auth_headers
    )
    assert list_res.status_code == 200
    assert any(m["id"] == sms_id for m in list_res.json())

from datetime import datetime, timezone
import pytest


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


def test_cash_sale_exact(client, auth_headers):
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 600.0,
            "payment_method": "cash",
        },
    )
    assert res.status_code in (200, 201), res.json()
    data = res.json()
    assert data["amount"] == "600.00"
    assert data["amount_received"] == "600.00"
    assert data["change_amount"] == "0.00"
    assert data["payment_method"] == "cash"
    assert data["mpesa_message_id"] is None
    assert len(data["effects"]) == 1
    assert data["effects"][0]["account_type"] == "cash"
    assert data["effects"][0]["direction"] == "credit"
    assert data["effects"][0]["amount"] == "600.00"


def test_cash_sale_overpayment(client, auth_headers):
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 600.0,
            "amount_received": 1000.0,
            "payment_method": "cash",
        },
    )
    assert res.status_code in (200, 201), res.json()
    data = res.json()
    assert data["amount"] == "600.00"
    assert data["amount_received"] == "1000.00"
    assert data["change_amount"] == "400.00"
    assert data["payment_method"] == "cash"
    # Ledger receives net Cash +600
    assert len(data["effects"]) == 1
    assert data["effects"][0]["account_type"] == "cash"
    assert data["effects"][0]["direction"] == "credit"
    assert data["effects"][0]["amount"] == "600.00"


def test_cash_sale_with_sms_rejected(client, auth_headers):
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 600.0,
            "payment_method": "cash",
            "mpesa_message_id": 1,
        },
    )
    assert res.status_code == 422
    assert "M-Pesa SMS cannot be attached to a cash sale" in res.json()["detail"]


def test_underpayment_rejected(client, auth_headers):
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 600.0,
            "amount_received": 500.0,
            "payment_method": "cash",
        },
    )
    assert res.status_code == 422
    assert "Amount received cannot be less than sale amount" in res.json()["detail"]


def test_mpesa_sale_exact_with_sms(client, auth_headers):
    _complete_onboarding(client, auth_headers)

    # Ingest SMS
    sms_res = client.post(
        "/api/v1/mpesa/messages",
        headers=auth_headers,
        json={
            "reference": "ABC123",
            "sender": "Customer X",
            "amount": 600.0,
            "direction": "MONEY_RECEIVED",
            "raw_text": "Received KSh600 from Customer X ABC123",
            "message_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert sms_res.status_code == 201, sms_res.json()
    sms_id = sms_res.json()["id"]

    # Verify SMS listed in unused
    list_res = client.get("/api/v1/mpesa/messages?direction=MONEY_RECEIVED&unused=true", headers=auth_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1
    assert list_res.json()[0]["id"] == sms_id

    # Create M-Pesa sale using SMS
    sale_res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 600.0,
            "payment_method": "mpesa",
            "mpesa_message_id": sms_id,
        },
    )
    assert sale_res.status_code in (200, 201), sale_res.json()
    data = sale_res.json()
    assert data["amount"] == "600.00"
    assert data["payment_method"] == "mpesa"
    assert data["mpesa_message_id"] == sms_id
    assert len(data["effects"]) == 1
    assert data["effects"][0]["account_type"] == "float"
    assert data["effects"][0]["direction"] == "credit"
    assert data["effects"][0]["amount"] == "600.00"

    # Verify SMS is now used and no longer returned in unused query
    list_res2 = client.get("/api/v1/mpesa/messages?direction=MONEY_RECEIVED&unused=true", headers=auth_headers)
    assert list_res2.status_code == 200
    assert len(list_res2.json()) == 0


def test_mpesa_sale_overpayment_with_sms(client, auth_headers):
    _complete_onboarding(client, auth_headers)

    # Ingest SMS of 1000
    sms_res = client.post(
        "/api/v1/mpesa/messages",
        headers=auth_headers,
        json={
            "reference": "XYZ456",
            "sender": "Customer Y",
            "amount": 1000.0,
            "direction": "MONEY_RECEIVED",
            "raw_text": "Received KSh1,000 from Customer Y XYZ456",
            "message_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert sms_res.status_code == 201
    sms_id = sms_res.json()["id"]

    # Create M-Pesa sale of 600 with received 1000
    sale_res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 600.0,
            "amount_received": 1000.0,
            "payment_method": "mpesa",
            "mpesa_message_id": sms_id,
        },
    )
    assert sale_res.status_code in (200, 201), sale_res.json()
    data = sale_res.json()
    assert data["amount"] == "600.00"
    assert data["amount_received"] == "1000.00"
    assert data["change_amount"] == "400.00"
    assert data["payment_method"] == "mpesa"
    assert data["mpesa_message_id"] == sms_id

    # Verify Ledger entries: Float +1000 credit, Cash -400 debit
    effects = data["effects"]
    assert len(effects) == 2
    float_effect = next(e for e in effects if e["account_type"] == "float")
    cash_effect = next(e for e in effects if e["account_type"] == "cash")
    assert float_effect["direction"] == "credit"
    assert float_effect["amount"] == "1000.00"
    assert cash_effect["direction"] == "debit"
    assert cash_effect["amount"] == "400.00"


def test_reuse_already_linked_sms_rejected(client, auth_headers):
    _complete_onboarding(client, auth_headers)

    sms_res = client.post(
        "/api/v1/mpesa/messages",
        headers=auth_headers,
        json={
            "reference": "SINGLE1",
            "sender": "Customer Z",
            "amount": 500.0,
            "direction": "MONEY_RECEIVED",
            "raw_text": "Received KSh500 from Customer Z SINGLE1",
            "message_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    sms_id = sms_res.json()["id"]

    # First sale links SMS
    res1 = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "sale", "amount": 500.0, "payment_method": "mpesa", "mpesa_message_id": sms_id},
    )
    assert res1.status_code in (200, 201)

    # Second sale tries to reuse same SMS
    res2 = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "sale", "amount": 500.0, "payment_method": "mpesa", "mpesa_message_id": sms_id},
    )
    assert res2.status_code == 400
    assert "SMS is already linked to another transaction" in res2.json()["detail"]


def test_mpesa_sale_without_sms_succeeds(client, auth_headers):
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 800.0,
            "payment_method": "mpesa",
        },
    )
    assert res.status_code in (200, 201), res.json()
    data = res.json()
    assert data["amount"] == "800.00"
    assert data["payment_method"] == "mpesa"
    assert data["mpesa_message_id"] is None
    assert len(data["effects"]) == 1
    assert data["effects"][0]["account_type"] == "float"
    assert data["effects"][0]["direction"] == "credit"
    assert data["effects"][0]["amount"] == "800.00"


def _ingest_sms(client, auth_headers, reference, amount, sender="Customer"):
    res = client.post(
        "/api/v1/mpesa/messages",
        headers=auth_headers,
        json={
            "reference": reference,
            "sender": sender,
            "amount": amount,
            "direction": "MONEY_RECEIVED",
            "raw_text": f"Received KSh{amount} from {sender} {reference}",
            "message_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert res.status_code == 201, res.json()
    return res.json()["id"]


def test_mpesa_sale_batch_sms_groups_multiple_proofs(client, auth_headers):
    _complete_onboarding(client, auth_headers)

    ids = [
        _ingest_sms(client, auth_headers, "BATCH1", 200.0),
        _ingest_sms(client, auth_headers, "BATCH2", 300.0),
        _ingest_sms(client, auth_headers, "BATCH3", 150.0),
    ]

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 650.0,
            "amount_received": 650.0,
            "payment_method": "mpesa",
            "mpesa_message_ids": ids,
        },
    )
    assert res.status_code in (200, 201), res.json()
    data = res.json()
    assert data["amount"] == "650.00"
    assert data["amount_received"] == "650.00"
    assert data["mpesa_message_id"] == ids[0]
    assert [m["id"] for m in data["mpesa_messages"]] == ids
    assert len(data["effects"]) == 1
    assert data["effects"][0]["account_type"] == "float"
    assert data["effects"][0]["amount"] == "650.00"

    # All batch SMS are now used and no longer returned as unused
    list_res = client.get(
        "/api/v1/mpesa/messages?direction=MONEY_RECEIVED&unused=true",
        headers=auth_headers,
    )
    assert list_res.status_code == 200
    assert all(m["id"] not in ids for m in list_res.json())


def test_mpesa_sale_batch_ledger_sums_received(client, auth_headers):
    _complete_onboarding(client, auth_headers)

    ids = [
        _ingest_sms(client, auth_headers, "SUM1", 200.0),
        _ingest_sms(client, auth_headers, "SUM2", 300.0),
    ]

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 400.0,
            "amount_received": 500.0,
            "payment_method": "mpesa",
            "mpesa_message_ids": ids,
        },
    )
    assert res.status_code in (200, 201), res.json()
    data = res.json()
    assert data["amount_received"] == "500.00"
    assert data["change_amount"] == "100.00"
    float_effect = next(e for e in data["effects"] if e["account_type"] == "float")
    cash_effect = next(e for e in data["effects"] if e["account_type"] == "cash")
    assert float_effect["amount"] == "500.00"
    assert cash_effect["direction"] == "debit"
    assert cash_effect["amount"] == "100.00"


def test_mpesa_sale_batch_reuse_rejected(client, auth_headers):
    _complete_onboarding(client, auth_headers)

    first_id = _ingest_sms(client, auth_headers, "USED1", 200.0)
    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 200.0,
            "payment_method": "mpesa",
            "mpesa_message_id": first_id,
        },
    )
    assert res.status_code in (200, 201), res.json()

    fresh_id = _ingest_sms(client, auth_headers, "FRESH1", 300.0)
    res2 = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 500.0,
            "payment_method": "mpesa",
            "mpesa_message_ids": [first_id, fresh_id],
        },
    )
    assert res2.status_code == 400
    assert "SMS is already linked to another transaction" in res2.json()["detail"]


def test_cash_sale_with_batch_sms_rejected(client, auth_headers):
    _complete_onboarding(client, auth_headers)

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 600.0,
            "payment_method": "cash",
            "mpesa_message_ids": [1, 2],
        },
    )
    assert res.status_code == 422
    assert "M-Pesa SMS cannot be attached to a cash sale" in res.json()["detail"]

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


def test_any_direction_can_attach_to_any_type(client, auth_headers):
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

    # The picker toggle lets a user back a withdrawal with a Take SMS too.
    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "withdrawal", "amount": 5000.0, "mpesa_message_id": take_id},
    )
    assert res.status_code in (200, 201), res.json()
    assert res.json()["mpesa_message_id"] == take_id


def test_add_float_accepts_any_direction(client, auth_headers):
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

    # Give (MONEY_SENT) is also accepted for an add_float deposit.
    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={"type": "add_float", "amount": 5000.0, "mpesa_message_id": give_id},
    )
    assert res.status_code in (200, 201), res.json()
    assert res.json()["mpesa_message_id"] == give_id


def _create_account(client, auth_headers, name="Supplier ABC", **extra):
    res = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={"name": name, **extra},
    )
    assert res.status_code == 201, res.json()
    return res.json()


def _assert_transfer_linked(client, auth_headers, transaction_id, sms_id):
    txn = client.get(
        f"/api/v1/transactions/{transaction_id}", headers=auth_headers
    ).json()
    assert txn["mpesa_message_id"] == sms_id


def test_give_money_links_sms_proof(client, auth_headers):
    _complete_onboarding(client, auth_headers)
    sms_id = _ingest(client, auth_headers, "GIVE500", "MONEY_SENT")
    acct = _create_account(client, auth_headers)

    res = client.post(
        "/api/v1/tracked-accounts/give",
        headers=auth_headers,
        json={
            "source_type": "float",
            "tracked_account_id": acct["id"],
            "amount": 5000.0,
            "mpesa_message_id": sms_id,
        },
    )
    assert res.status_code == 201, res.json()
    _assert_transfer_linked(client, auth_headers, res.json()["transaction_id"], sms_id)

    # The linked SMS no longer shows up as unused.
    unused = client.get(
        "/api/v1/mpesa/messages?direction=MONEY_SENT&unused=true", headers=auth_headers
    ).json()
    assert all(m["id"] != sms_id for m in unused)


def test_get_money_back_links_sms_proof(client, auth_headers):
    _complete_onboarding(client, auth_headers)
    acct = _create_account(client, auth_headers)
    client.post(
        "/api/v1/tracked-accounts/give",
        headers=auth_headers,
        json={"source_type": "float", "tracked_account_id": acct["id"], "amount": 10000.0},
    )
    sms_id = _ingest(client, auth_headers, "TAKE200", "MONEY_RECEIVED")

    res = client.post(
        "/api/v1/tracked-accounts/get-back",
        headers=auth_headers,
        json={
            "tracked_account_id": acct["id"],
            "destination_type": "float",
            "amount": 4000.0,
            "mpesa_message_id": sms_id,
        },
    )
    assert res.status_code == 201, res.json()
    _assert_transfer_linked(client, auth_headers, res.json()["transaction_id"], sms_id)


def test_receive_money_links_sms_proof(client, auth_headers):
    _complete_onboarding(client, auth_headers)
    sms_id = _ingest(client, auth_headers, "TAKE500", "MONEY_RECEIVED")
    held = _create_account(client, auth_headers, name="Amar Deposit", position_type="held")

    res = client.post(
        "/api/v1/tracked-accounts/receive",
        headers=auth_headers,
        json={
            "tracked_account_id": held["id"],
            "destination_type": "cash",
            "amount": 5000.0,
            "mpesa_message_id": sms_id,
        },
    )
    assert res.status_code == 201, res.json()
    _assert_transfer_linked(client, auth_headers, res.json()["transaction_id"], sms_id)


def test_return_money_links_sms_proof(client, auth_headers):
    _complete_onboarding(client, auth_headers)
    held = _create_account(client, auth_headers, name="Amar Deposit", position_type="held")
    client.post(
        "/api/v1/tracked-accounts/receive",
        headers=auth_headers,
        json={"tracked_account_id": held["id"], "destination_type": "cash", "amount": 5000.0},
    )
    sms_id = _ingest(client, auth_headers, "GIVE500", "MONEY_SENT")

    res = client.post(
        "/api/v1/tracked-accounts/return",
        headers=auth_headers,
        json={
            "tracked_account_id": held["id"],
            "source_type": "cash",
            "amount": 5000.0,
            "mpesa_message_id": sms_id,
        },
    )
    assert res.status_code == 201, res.json()
    _assert_transfer_linked(client, auth_headers, res.json()["transaction_id"], sms_id)


def test_transfer_rejects_foreign_business_sms(client, auth_headers):
    _complete_onboarding(client, auth_headers)
    acct = _create_account(client, auth_headers)

    # User B (separate business) ingests an SMS.
    user_b = client.post(
        "/api/v1/auth/register",
        json={"email": "userb@example.com", "password": "Password123", "full_name": "User B"},
    ).json()
    token_b = client.post(
        "/api/v1/auth/login",
        json={"email": "userb@example.com", "password": "Password123"},
    ).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    _complete_onboarding(client, headers_b)
    foreign_sms = _ingest(client, headers_b, "GIVE500", "MONEY_SENT")

    res = client.post(
        "/api/v1/tracked-accounts/give",
        headers=auth_headers,
        json={
            "source_type": "float",
            "tracked_account_id": acct["id"],
            "amount": 5000.0,
            "mpesa_message_id": foreign_sms,
        },
    )
    assert res.status_code == 404, res.json()

    # The whole transfer rolled back - no activity recorded.
    dash = client.get("/api/v1/dashboard/", headers=auth_headers).json()
    assert dash["today_activity"] == []


def test_transfer_rejects_already_linked_sms(client, auth_headers):
    _complete_onboarding(client, auth_headers)
    sms_id = _ingest(client, auth_headers, "GIVE500", "MONEY_SENT")
    acct_a = _create_account(client, auth_headers, name="Account A")
    acct_b = _create_account(client, auth_headers, name="Account B")

    res = client.post(
        "/api/v1/tracked-accounts/give",
        headers=auth_headers,
        json={
            "source_type": "float",
            "tracked_account_id": acct_a["id"],
            "amount": 5000.0,
            "mpesa_message_id": sms_id,
        },
    )
    assert res.status_code == 201, res.json()

    res = client.post(
        "/api/v1/tracked-accounts/give",
        headers=auth_headers,
        json={
            "source_type": "float",
            "tracked_account_id": acct_b["id"],
            "amount": 5000.0,
            "mpesa_message_id": sms_id,
        },
    )
    assert res.status_code == 400, res.json()

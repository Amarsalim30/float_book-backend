import pytest
from datetime import datetime, timezone


def _complete_onboarding(client, auth_headers):
    res = client.post(
        "/api/v1/onboarding/complete",
        headers=auth_headers,
        json={
            "business_name": "Reuse Test Shop",
            "opening_cash": 10000.0,
            "opening_float": 50000.0,
        },
    )
    assert res.status_code in (200, 201), res.json()


def _ingest_sms(client, auth_headers, reference, direction="MONEY_RECEIVED", amount=5000.0):
    res = client.post(
        "/api/v1/mpesa/messages",
        headers=auth_headers,
        json={
            "reference": reference,
            "sender": "Test Customer",
            "amount": amount,
            "direction": direction,
            "raw_text": f"raw {direction} {amount} ref {reference}",
            "message_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert res.status_code == 201, res.json()
    return res.json()["id"]


def _get_unused_ids(client, auth_headers, direction="MONEY_RECEIVED"):
    res = client.get(
        f"/api/v1/mpesa/messages?direction={direction}&unused=true",
        headers=auth_headers,
    )
    assert res.status_code == 200, res.json()
    return [m["id"] for m in res.json()]


def test_single_sms_attach_and_detach_on_edit(client, auth_headers):
    """Verify that removing a single SMS from a transaction via edit releases it for reuse."""
    _complete_onboarding(client, auth_headers)
    sms_id = _ingest_sms(client, auth_headers, "REF_SINGLE_01")
    assert sms_id in _get_unused_ids(client, auth_headers)

    # 1. Create transaction with SMS attached
    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 5000.0,
            "payment_method": "mpesa",
            "mpesa_message_id": sms_id,
        },
    )
    assert res.status_code == 201, res.json()
    txn_id = res.json()["id"]

    # SMS is now used
    assert sms_id not in _get_unused_ids(client, auth_headers)

    # 2. Edit transaction and remove SMS (mpesa_message_id = None)
    edit_res = client.put(
        f"/api/v1/transactions/{txn_id}",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 5000.0,
            "payment_method": "mpesa",
            "mpesa_message_id": None,
        },
    )
    assert edit_res.status_code == 200, edit_res.json()
    assert edit_res.json()["mpesa_message_id"] is None

    # SMS is now unused again!
    assert sms_id in _get_unused_ids(client, auth_headers)

    # 3. Re-attach SMS to a new transaction
    txn2_res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 5000.0,
            "payment_method": "mpesa",
            "mpesa_message_id": sms_id,
        },
    )
    assert txn2_res.status_code == 201, txn2_res.json()
    assert txn2_res.json()["mpesa_message_id"] == sms_id


def test_single_sms_detach_on_delete(client, auth_headers):
    """Verify that deleting a transaction releases its attached SMS for reuse."""
    _complete_onboarding(client, auth_headers)
    sms_id = _ingest_sms(client, auth_headers, "REF_DEL_01", direction="MONEY_SENT")

    # Attach to transaction
    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "withdrawal",
            "amount": 5000.0,
            "mpesa_message_id": sms_id,
        },
    )
    txn_id = res.json()["id"]
    assert sms_id not in _get_unused_ids(client, auth_headers, direction="MONEY_SENT")

    # Delete transaction
    del_res = client.delete(f"/api/v1/transactions/{txn_id}", headers=auth_headers)
    assert del_res.status_code == 204

    # SMS is available again
    assert sms_id in _get_unused_ids(client, auth_headers, direction="MONEY_SENT")


def test_multiple_sms_partial_and_full_detach_on_edit(client, auth_headers):
    """Verify batch SMS attaching, partial detachment, and full detachment on edit."""
    _complete_onboarding(client, auth_headers)
    sms1 = _ingest_sms(client, auth_headers, "REF_BATCH_1", amount=2000.0)
    sms2 = _ingest_sms(client, auth_headers, "REF_BATCH_2", amount=3000.0)
    sms3 = _ingest_sms(client, auth_headers, "REF_BATCH_3", amount=1000.0)

    # 1. Attach 3 SMS messages to a sale
    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 6000.0,
            "amount_received": 6000.0,
            "payment_method": "mpesa",
            "mpesa_message_ids": [sms1, sms2, sms3],
        },
    )
    assert res.status_code == 201, res.json()
    txn_id = res.json()["id"]

    unused = _get_unused_ids(client, auth_headers)
    assert sms1 not in unused and sms2 not in unused and sms3 not in unused

    # 2. Edit to keep only [sms1, sms3] (removing sms2)
    edit_res = client.put(
        f"/api/v1/transactions/{txn_id}",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 6000.0,
            "amount_received": 6000.0,
            "payment_method": "mpesa",
            "mpesa_message_ids": [sms1, sms3],
        },
    )
    assert edit_res.status_code == 200, edit_res.json()
    unused_after_partial = _get_unused_ids(client, auth_headers)
    assert sms2 in unused_after_partial  # sms2 released
    assert sms1 not in unused_after_partial and sms3 not in unused_after_partial  # sms1 & sms3 still linked

    # 3. Edit to clear all SMS (mpesa_message_ids = [])
    edit_clear_res = client.put(
        f"/api/v1/transactions/{txn_id}",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 6000.0,
            "amount_received": 6000.0,
            "payment_method": "mpesa",
            "mpesa_message_ids": [],
        },
    )
    assert edit_clear_res.status_code == 200, edit_clear_res.json()
    unused_after_clear = _get_unused_ids(client, auth_headers)
    assert sms1 in unused_after_clear and sms2 in unused_after_clear and sms3 in unused_after_clear


def test_multiple_sms_detach_on_delete(client, auth_headers):
    """Verify deleting a multi-SMS transaction releases all attached SMS messages."""
    _complete_onboarding(client, auth_headers)
    sms1 = _ingest_sms(client, auth_headers, "REF_DEL_BATCH_1")
    sms2 = _ingest_sms(client, auth_headers, "REF_DEL_BATCH_2")

    res = client.post(
        "/api/v1/transactions/",
        headers=auth_headers,
        json={
            "type": "sale",
            "amount": 10000.0,
            "amount_received": 10000.0,
            "payment_method": "mpesa",
            "mpesa_message_ids": [sms1, sms2],
        },
    )
    txn_id = res.json()["id"]

    del_res = client.delete(f"/api/v1/transactions/{txn_id}", headers=auth_headers)
    assert del_res.status_code == 204

    unused = _get_unused_ids(client, auth_headers)
    assert sms1 in unused and sms2 in unused


def test_transfer_transaction_sms_detach_on_edit_and_delete(client, auth_headers):
    """Verify transfer/tracked-account transactions release SMS on edit detachment and deletion."""
    _complete_onboarding(client, auth_headers)
    sms_id = _ingest_sms(client, auth_headers, "REF_TRANSFER_1", direction="MONEY_SENT")

    acct_res = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={"name": "Supplier X"},
    )
    acct_id = acct_res.json()["id"]

    # Give money with SMS
    give_res = client.post(
        "/api/v1/tracked-accounts/give",
        headers=auth_headers,
        json={
            "source_type": "float",
            "tracked_account_id": acct_id,
            "amount": 5000.0,
            "mpesa_message_id": sms_id,
        },
    )
    assert give_res.status_code == 201, give_res.json()
    txn_id = give_res.json()["transaction_id"]

    assert sms_id not in _get_unused_ids(client, auth_headers, direction="MONEY_SENT")

    # Edit transfer transaction and remove SMS
    edit_res = client.put(
        f"/api/v1/transactions/{txn_id}",
        headers=auth_headers,
        json={
            "type": "transfer",
            "amount": 5000.0,
            "mpesa_message_id": None,
        },
    )
    assert edit_res.status_code == 200, edit_res.json()
    assert edit_res.json()["mpesa_message_id"] is None
    assert sms_id in _get_unused_ids(client, auth_headers, direction="MONEY_SENT")

    # Re-attach SMS to transfer
    edit_reattach_res = client.put(
        f"/api/v1/transactions/{txn_id}",
        headers=auth_headers,
        json={
            "type": "transfer",
            "amount": 5000.0,
            "mpesa_message_id": sms_id,
        },
    )
    assert edit_reattach_res.status_code == 200, edit_reattach_res.json()
    assert sms_id not in _get_unused_ids(client, auth_headers, direction="MONEY_SENT")

    # Delete transfer transaction
    del_res = client.delete(f"/api/v1/transactions/{txn_id}", headers=auth_headers)
    assert del_res.status_code == 204
    assert sms_id in _get_unused_ids(client, auth_headers, direction="MONEY_SENT")

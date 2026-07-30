"""
Tests for the Tracked Accounts ("Money I Track") and Transfers module.
"""

def _complete_onboarding(client, auth_headers, cash=10000.0, float_bal=50000.0):
    res = client.post(
        "/api/v1/onboarding/complete",
        headers=auth_headers,
        json={
            "business_name": "Test Shop",
            "opening_cash": cash,
            "opening_float": float_bal,
        },
    )
    assert res.status_code in (200, 201), res.json()


def test_create_and_list_tracked_account(client, auth_headers):
    _complete_onboarding(client, auth_headers)

    # 1. Create account
    create_res = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={
            "name": "Amar Salim",
            "account_type": "person",
            "phone": "0712345678",
            "notes": "Regular borrower",
        },
    )
    assert create_res.status_code == 201, create_res.json()
    account = create_res.json()
    assert account["name"] == "Amar Salim"
    assert account["account_type"] == "person"
    assert float(account["balance"]) == 0.0

    # 2. List accounts
    list_res = client.get("/api/v1/tracked-accounts/", headers=auth_headers)
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == account["id"]


def test_give_money_and_get_money_back_flow(client, auth_headers):
    _complete_onboarding(client, auth_headers, cash=10000.0, float_bal=50000.0)

    # Create account
    acct = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={"name": "Supplier ABC", "account_type": "business"},
    ).json()
    acct_id = acct["id"]

    # 1. Give Money: Float (50,000) -> Supplier ABC (25,000)
    give_res = client.post(
        "/api/v1/tracked-accounts/give",
        headers=auth_headers,
        json={
            "source_type": "float",
            "tracked_account_id": acct_id,
            "amount": 25000.0,
            "note": "Advance for inventory",
        },
    )
    assert give_res.status_code == 201, give_res.json()

    # Verify Supplier ABC balance is 25,000
    detail = client.get(
        f"/api/v1/tracked-accounts/{acct_id}", headers=auth_headers
    ).json()
    assert float(detail["balance"]) == 25000.0
    assert len(detail["history"]) == 1

    # Verify Float balance dropped to 25,000 (50,000 - 25,000)
    dash = client.get("/api/v1/dashboard/", headers=auth_headers).json()
    assert float(dash["float_balance"]) == 25000.0

    # 2. Get Money Back: Supplier ABC -> Float (10,000)
    get_res = client.post(
        "/api/v1/tracked-accounts/get-back",
        headers=auth_headers,
        json={
            "tracked_account_id": acct_id,
            "destination_type": "float",
            "amount": 10000.0,
            "note": "Partial return",
        },
    )
    assert get_res.status_code == 201, get_res.json()

    # Verify Supplier ABC balance is now 15,000 (25,000 - 10,000)
    detail2 = client.get(
        f"/api/v1/tracked-accounts/{acct_id}", headers=auth_headers
    ).json()
    assert float(detail2["balance"]) == 15000.0
    assert len(detail2["history"]) == 2

    # Verify Float balance recovered to 35,000 (25,000 + 10,000)
    dash2 = client.get("/api/v1/dashboard/", headers=auth_headers).json()
    assert float(dash2["float_balance"]) == 35000.0


def test_overdraft_prevention_on_get_money_back(client, auth_headers):
    _complete_onboarding(client, auth_headers)

    acct = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={"name": "Amar", "account_type": "person"},
    ).json()
    acct_id = acct["id"]

    # Give 5,000
    client.post(
        "/api/v1/tracked-accounts/give",
        headers=auth_headers,
        json={
            "source_type": "cash",
            "tracked_account_id": acct_id,
            "amount": 5000.0,
        },
    )

    # Attempt to get back 10,000 (exceeding balance of 5,000)
    bad_res = client.post(
        "/api/v1/tracked-accounts/get-back",
        headers=auth_headers,
        json={
            "tracked_account_id": acct_id,
            "destination_type": "cash",
            "amount": 10000.0,
        },
    )
    assert bad_res.status_code == 400
    detail = bad_res.json()["detail"]
    assert detail["error"] == "insufficient_tracked_balance"
    assert detail["available"] == 5000.0
    assert detail["requested"] == 10000.0

    # Verify balance remains unchanged at 5,000
    check = client.get(
        f"/api/v1/tracked-accounts/{acct_id}", headers=auth_headers
    ).json()
    assert float(check["balance"]) == 5000.0


def test_multi_tenant_isolation(client, auth_headers):
    """Business A cannot view or transfer money from Business B's account."""
    _complete_onboarding(client, auth_headers)

    # Business A creates account
    acct_a = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={"name": "Business A Friend"},
    ).json()

    # Register and onboarding for User B
    user_b_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": "userb@example.com",
            "password": "Password123",
            "full_name": "User B",
        },
    ).json()
    token_b = client.post(
        "/api/v1/auth/login",
        json={"email": "userb@example.com", "password": "Password123"},
    ).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    _complete_onboarding(client, headers_b)

    # User B attempts to access User A's account
    get_res = client.get(
        f"/api/v1/tracked-accounts/{acct_a['id']}", headers=headers_b
    )
    assert get_res.status_code == 404

    # User B attempts to give money to User A's account
    give_res = client.post(
        "/api/v1/tracked-accounts/give",
        headers=headers_b,
        json={
            "source_type": "float",
            "tracked_account_id": acct_a["id"],
            "amount": 1000.0,
        },
    )
    assert give_res.status_code == 404

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

    # Today's activity shows a single transfer TO the account (money out)
    give_activity = dash["today_activity"][0]
    assert give_activity["type"] == "transfer"
    assert give_activity["direction"] == "out"
    assert give_activity["counterparty_name"] == "Supplier ABC"
    assert float(give_activity["amount"]) == 25000.0

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
    assert float(detail2["given"]) == 25000.0
    assert float(detail2["returned"]) == 10000.0
    assert detail2["last_transaction"] is not None
    assert len(detail2["history"]) == 2

    # History is returned newest first:
    # Most recent entry (Get Money Back 10,000 debit): running_balance = 15000.0
    # First entry (Give Money 25,000 credit): running_balance = 25000.0
    assert detail2["history"][0]["entry_type"] == "debit"
    assert float(detail2["history"][0]["running_balance"]) == 15000.0
    assert detail2["history"][1]["entry_type"] == "credit"
    assert float(detail2["history"][1]["running_balance"]) == 25000.0

    # Verify Float balance recovered to 35,000 (25,000 + 10,000)
    dash2 = client.get("/api/v1/dashboard/", headers=auth_headers).json()
    assert float(dash2["float_balance"]) == 35000.0

    # Today's activity now shows a single transfer FROM the account (money in)
    get_back_activity = dash2["today_activity"][0]
    assert get_back_activity["type"] == "transfer"
    assert get_back_activity["direction"] == "in"
    assert get_back_activity["counterparty_name"] == "Supplier ABC"
    assert float(get_back_activity["amount"]) == 10000.0



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


def test_receive_and_return_money_flow(client, auth_headers):
    _complete_onboarding(client, auth_headers, cash=10000.0, float_bal=50000.0)

    # Create held account position
    acct = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={"name": "Amar Deposit", "position_type": "held"},
    ).json()
    acct_id = acct["id"]

    # 1. Receive Money: Amar -> Cash (10,000)
    rec_res = client.post(
        "/api/v1/tracked-accounts/receive",
        headers=auth_headers,
        json={
            "tracked_account_id": acct_id,
            "destination_type": "cash",
            "amount": 10000.0,
            "note": "Customer deposit",
        },
    )
    assert rec_res.status_code == 201, rec_res.json()

    # Held balance is now 10,000
    detail = client.get(
        f"/api/v1/tracked-accounts/{acct_id}", headers=auth_headers
    ).json()
    assert float(detail["balance"]) == 10000.0

    # Dashboard cash balance increased to 20,000 (10,000 + 10,000)
    dash = client.get("/api/v1/dashboard/", headers=auth_headers).json()
    assert float(dash["cash_balance"]) == 20000.0

    # Today's activity shows a single transfer FROM the contact (money in, held)
    rec_activity = dash["today_activity"][0]
    assert rec_activity["type"] == "transfer"
    assert rec_activity["direction"] == "in"
    assert rec_activity["counterparty_name"] == "Amar Deposit"
    assert float(rec_activity["amount"]) == 10000.0

    # 2. Return Money: Cash -> Amar (4,000)
    ret_res = client.post(
        "/api/v1/tracked-accounts/return",
        headers=auth_headers,
        json={
            "tracked_account_id": acct_id,
            "source_type": "cash",
            "amount": 4000.0,
            "note": "Partial return of deposit",
        },
    )
    assert ret_res.status_code == 201, ret_res.json()

    # Held balance is now 6,000 (10,000 - 4,000)
    detail2 = client.get(
        f"/api/v1/tracked-accounts/{acct_id}", headers=auth_headers
    ).json()
    assert float(detail2["balance"]) == 6000.0

    # Dashboard cash balance decreased to 16,000 (20,000 - 4,000)
    dash2 = client.get("/api/v1/dashboard/", headers=auth_headers).json()
    assert float(dash2["cash_balance"]) == 16000.0

    # Today's activity now shows a single transfer TO the contact (money out, held)
    ret_activity = dash2["today_activity"][0]
    assert ret_activity["type"] == "transfer"
    assert ret_activity["direction"] == "out"
    assert ret_activity["counterparty_name"] == "Amar Deposit"
    assert float(ret_activity["amount"]) == 4000.0


def test_critical_no_netting_positions(client, auth_headers):
    """
    Test strict dual position separation (No Netting):
    Amar has Money I Track = 25,000 and Money Held = 10,000.
    Operations on one position NEVER mutate the other.
    """
    _complete_onboarding(client, auth_headers, cash=100000.0, float_bal=100000.0)

    # Create Person
    p_res = client.post(
        "/api/v1/people/",
        json={"name": "Amar", "type": "customer"},
    )
    assert p_res.status_code == 201
    person_id = p_res.json()["id"]

    # Create Money I Track position
    tracked_acct = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={
            "name": "Amar",
            "position_type": "tracked",
            "person_id": person_id,
        },
    ).json()

    # Create Money Held position
    held_acct = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={
            "name": "Amar",
            "position_type": "held",
            "person_id": person_id,
        },
    ).json()

    # 1. Give Money: 25,000 to Money I Track
    client.post(
        "/api/v1/tracked-accounts/give",
        headers=auth_headers,
        json={
            "source_type": "cash",
            "tracked_account_id": tracked_acct["id"],
            "amount": 25000.0,
        },
    )

    # 2. Receive Money: 10,000 into Money Held
    client.post(
        "/api/v1/tracked-accounts/receive",
        headers=auth_headers,
        json={
            "destination_type": "cash",
            "tracked_account_id": held_acct["id"],
            "amount": 10000.0,
        },
    )

    # Assert initial balances: Tracked = 25,000, Held = 10,000
    t_bal = float(client.get(f"/api/v1/tracked-accounts/{tracked_acct['id']}", headers=auth_headers).json()["balance"])
    h_bal = float(client.get(f"/api/v1/tracked-accounts/{held_acct['id']}", headers=auth_headers).json()["balance"])
    assert t_bal == 25000.0
    assert h_bal == 10000.0

    # 3. Get Money Back = 10,000 from Money I Track
    client.post(
        "/api/v1/tracked-accounts/get-back",
        headers=auth_headers,
        json={
            "tracked_account_id": tracked_acct["id"],
            "destination_type": "cash",
            "amount": 10000.0,
        },
    )

    # Expected: Money I Track = 15,000, Money Held = 10,000 (held unchanged)
    t_bal2 = float(client.get(f"/api/v1/tracked-accounts/{tracked_acct['id']}", headers=auth_headers).json()["balance"])
    h_bal2 = float(client.get(f"/api/v1/tracked-accounts/{held_acct['id']}", headers=auth_headers).json()["balance"])
    assert t_bal2 == 15000.0
    assert h_bal2 == 10000.0

    # 4. Return Money = 5,000 from Money Held
    client.post(
        "/api/v1/tracked-accounts/return",
        headers=auth_headers,
        json={
            "tracked_account_id": held_acct["id"],
            "source_type": "cash",
            "amount": 5000.0,
        },
    )

    # Expected: Money I Track = 15,000 (tracked unchanged), Money Held = 5,000
    t_bal3 = float(client.get(f"/api/v1/tracked-accounts/{tracked_acct['id']}", headers=auth_headers).json()["balance"])
    h_bal3 = float(client.get(f"/api/v1/tracked-accounts/{held_acct['id']}", headers=auth_headers).json()["balance"])
    assert t_bal3 == 15000.0
    assert h_bal3 == 5000.0


def test_person_id_transfer_auto_creation_and_routing(client, auth_headers):
    _complete_onboarding(client, auth_headers, cash=50000.0, float_bal=50000.0)

    # 1. Create a person (contact)
    p_res = client.post(
        "/api/v1/people/",
        headers=auth_headers,
        json={"name": "Sarah Contact", "phone": "0700111222", "type": "customer"},
    ).json()
    person_id = p_res["id"]

    # 2. Receive Money passing person_id (no held position exists yet)
    rec_res = client.post(
        "/api/v1/tracked-accounts/receive",
        headers=auth_headers,
        json={
            "person_id": person_id,
            "destination_type": "cash",
            "amount": 7500.0,
        },
    )
    assert rec_res.status_code == 201, rec_res.json()

    # Verify person summary now reflects Money Held = 7,500
    person_detail = client.get(f"/api/v1/people/{person_id}", headers=auth_headers).json()
    assert float(person_detail["money_held"]["balance"]) == 7500.0

    # 3. Give Money passing person_id (no tracked position exists yet)
    give_res = client.post(
        "/api/v1/tracked-accounts/give",
        headers=auth_headers,
        json={
            "person_id": person_id,
            "source_type": "cash",
            "amount": 12000.0,
        },
    )
    assert give_res.status_code == 201, give_res.json()

    # Verify person summary now reflects Money Tracked = 12,000 and Money Held = 7,500 independently
    person_detail2 = client.get(f"/api/v1/people/{person_id}", headers=auth_headers).json()
    assert float(person_detail2["money_i_track"]["balance"]) == 12000.0
    assert float(person_detail2["money_held"]["balance"]) == 7500.0


def test_give_money_via_held_account_reuses_standalone_tracked_position(
    client, auth_headers
):
    """A held account can create, then repeatedly resolve, its tracked counterpart."""
    _complete_onboarding(client, auth_headers, cash=10000.0, float_bal=0.0)

    held = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={"name": "Amar", "position_type": "held"},
    ).json()

    for _ in range(2):
        response = client.post(
            "/api/v1/tracked-accounts/give",
            headers=auth_headers,
            json={
                "source_type": "cash",
                "tracked_account_id": held["id"],
                "amount": 1000.0,
            },
        )
        assert response.status_code == 201, response.json()

    contacts = client.get(
        "/api/v1/tracked-accounts/contacts", headers=auth_headers
    ).json()
    assert contacts["total"] == 1
    amar = contacts["items"][0]
    assert amar["held_position"]["account_id"] == held["id"]
    assert amar["tracked_position"] is not None

    tracked_id = amar["tracked_position"]["account_id"]
    tracked = client.get(
        f"/api/v1/tracked-accounts/{tracked_id}", headers=auth_headers
    ).json()
    assert float(tracked["balance"]) == 2000.0


def test_contacts_endpoint_groups_positions_and_totals(client, auth_headers):
    """The /tracked-accounts/contacts endpoint owns grouping + KPI totals for the UI."""
    _complete_onboarding(client, auth_headers, cash=100000.0, float_bal=100000.0)

    # Person-backed contact with BOTH positions
    p_res = client.post(
        "/api/v1/people/",
        headers=auth_headers,
        json={"name": "Amar", "type": "customer"},
    ).json()
    person_id = p_res["id"]

    tracked_acct = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={"name": "Amar", "position_type": "tracked", "person_id": person_id},
    ).json()
    held_acct = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={"name": "Amar", "position_type": "held", "person_id": person_id},
    ).json()

    # Standalone account (no Person record) must still appear
    standalone_acct = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={"name": "Supplier ABC", "account_type": "business"},
    ).json()

    # Build balances: give 25,000 to tracked, receive 10,000 into held, give 5,000 to standalone
    client.post(
        "/api/v1/tracked-accounts/give",
        headers=auth_headers,
        json={"source_type": "cash", "tracked_account_id": tracked_acct["id"], "amount": 25000.0},
    )
    client.post(
        "/api/v1/tracked-accounts/receive",
        headers=auth_headers,
        json={"destination_type": "cash", "tracked_account_id": held_acct["id"], "amount": 10000.0},
    )
    client.post(
        "/api/v1/tracked-accounts/give",
        headers=auth_headers,
        json={"source_type": "cash", "tracked_account_id": standalone_acct["id"], "amount": 5000.0},
    )

    res = client.get("/api/v1/tracked-accounts/contacts", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total"] == 2
    by_name = {c["name"]: c for c in data["items"]}

    amar = by_name["Amar"]
    assert amar["person_id"] == person_id
    assert amar["tracked_position"]["account_id"] == tracked_acct["id"]
    assert float(amar["tracked_position"]["balance"]) == 25000.0
    assert amar["held_position"]["account_id"] == held_acct["id"]
    assert float(amar["held_position"]["balance"]) == 10000.0

    supplier = by_name["Supplier ABC"]
    assert supplier["person_id"] is None
    assert float(supplier["tracked_position"]["balance"]) == 5000.0
    assert supplier["held_position"] is None

    # KPI totals are backend-derived (no client-side folding)
    totals = data["totals"]
    assert float(totals["tracked_total"]) == 30000.0
    assert float(totals["held_total"]) == 10000.0
    assert totals["tracked_count"] == 2
    assert totals["held_count"] == 1


def test_contacts_endpoint_empty_business(client, auth_headers):
    """No accounts -> empty items and zeroed totals (still 200, no crash)."""
    _complete_onboarding(client, auth_headers)

    res = client.get("/api/v1/tracked-accounts/contacts", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert float(data["totals"]["tracked_total"]) == 0.0
    assert float(data["totals"]["held_total"]) == 0.0
    assert data["totals"]["tracked_count"] == 0
    assert data["totals"]["held_count"] == 0


def test_create_account_is_idempotent_by_normalized_name_and_position(client, auth_headers):
    """Standalone accounts deduplicate by business, position, and normalized name."""
    _complete_onboarding(client, auth_headers, cash=100000.0, float_bal=100000.0)

    amar_caps = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={"name": "Amar", "account_type": "person"},
    ).json()
    amar_lower = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={"name": "amar", "account_type": "person"},
    ).json()

    # Same name + same position resolves to the existing account.
    zeinab_a = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={"name": "zeinab", "position_type": "tracked"},
    ).json()
    zeinab_b = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={"name": "zeinab", "position_type": "tracked"},
    ).json()

    # Same name tracked + held pair merges into one dual-position contact
    nahid_tracked = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={"name": "nahid", "position_type": "tracked"},
    ).json()
    nahid_held = client.post(
        "/api/v1/tracked-accounts/",
        headers=auth_headers,
        json={"name": "nahid", "position_type": "held"},
    ).json()

    res = client.get("/api/v1/tracked-accounts/contacts", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()

    assert amar_caps["id"] == amar_lower["id"]
    assert zeinab_a["id"] == zeinab_b["id"]

    # Case variants resolve to the original display name and account.
    names = [c["name"] for c in data["items"]]
    assert names.count("Amar") == 1
    assert "amar" not in names

    by_name = {}
    for c in data["items"]:
        by_name.setdefault(c["name"], []).append(c)

    amar_caps_item = by_name["Amar"][0]
    assert amar_caps_item["tracked_position"]["account_id"] == amar_caps["id"]

    # There is one normalized-name tracked position for zeinab.
    zeinab_items = by_name["zeinab"]
    assert len(zeinab_items) == 1
    zeinab_ids = {c["tracked_position"]["account_id"] for c in zeinab_items}
    assert zeinab_ids == {zeinab_a["id"]}

    # 'nahid' tracked+held merged into one dual-position contact
    assert len(by_name["nahid"]) == 1
    nahid = by_name["nahid"][0]
    assert nahid["tracked_position"]["account_id"] == nahid_tracked["id"]
    assert nahid["held_position"]["account_id"] == nahid_held["id"]

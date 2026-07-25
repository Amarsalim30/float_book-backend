"""
Tests for the Authentication module:
  POST /api/v1/auth/register
  POST /api/v1/auth/login
  POST /api/v1/auth/login/form
  GET  /api/v1/auth/me
"""
import pytest

from tests.conftest import VALID_USER

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
LOGIN_FORM_URL = "/api/v1/auth/login/form"
ME_URL = "/api/v1/auth/me"


# ===========================================================================
# POST /auth/register
# ===========================================================================

class TestRegister:
    def test_register_success(self, client):
        """A valid payload should create a user and return 201 with user data."""
        response = client.post(REGISTER_URL, json=VALID_USER)
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == VALID_USER["email"]
        assert data["full_name"] == VALID_USER["full_name"]
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        # Password must NOT appear in the response
        assert "password" not in data
        assert "hashed_password" not in data

    def test_register_email_normalised(self, client):
        """Email should be lower-cased and trimmed before storage."""
        payload = {**VALID_USER, "email": "  TEST@Example.COM  "}
        response = client.post(REGISTER_URL, json=payload)
        assert response.status_code == 201
        assert response.json()["email"] == "test@example.com"

    def test_register_duplicate_email_returns_400(self, client):
        """Registering the same email twice must fail with 400."""
        client.post(REGISTER_URL, json=VALID_USER)
        response = client.post(REGISTER_URL, json=VALID_USER)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    def test_register_invalid_email_returns_422(self, client):
        """An invalid email format must be rejected with 422."""
        response = client.post(
            REGISTER_URL,
            json={**VALID_USER, "email": "not-an-email"},
        )
        assert response.status_code == 422

    def test_register_short_password_returns_422(self, client):
        """Password shorter than 8 characters must be rejected with 422."""
        response = client.post(
            REGISTER_URL,
            json={**VALID_USER, "password": "short"},
        )
        assert response.status_code == 422

    def test_register_without_full_name(self, client):
        """full_name is optional — omitting it should succeed."""
        payload = {"email": "nofullname@example.com", "password": "ValidPass1!"}
        response = client.post(REGISTER_URL, json=payload)
        assert response.status_code == 201
        assert response.json()["full_name"] is None

    def test_register_missing_email_returns_422(self, client):
        """Omitting the email field must return 422."""
        response = client.post(REGISTER_URL, json={"password": "ValidPass1!"})
        assert response.status_code == 422

    def test_register_missing_password_returns_422(self, client):
        """Omitting the password field must return 422."""
        response = client.post(REGISTER_URL, json={"email": "a@b.com"})
        assert response.status_code == 422


# ===========================================================================
# POST /auth/login  (JSON body)
# ===========================================================================

class TestLogin:
    def test_login_success_returns_token(self, client, registered_user):
        """Valid credentials must return a bearer token."""
        response = client.post(
            LOGIN_URL,
            json={"email": VALID_USER["email"], "password": VALID_USER["password"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 20  # sanity check it's a real JWT

    def test_login_wrong_password_returns_401(self, client, registered_user):
        """Incorrect password must return 401 Unauthorized."""
        response = client.post(
            LOGIN_URL,
            json={"email": VALID_USER["email"], "password": "WrongPassword!"},
        )
        assert response.status_code == 401

    def test_login_unknown_email_returns_401(self, client):
        """Login with an unregistered email must return 401."""
        response = client.post(
            LOGIN_URL,
            json={"email": "ghost@example.com", "password": "SomePass1!"},
        )
        assert response.status_code == 401

    def test_login_wrong_password_does_not_reveal_user_existence(
        self, client, registered_user
    ):
        """
        The 401 message for unknown user vs wrong password should be identical
        to prevent user enumeration.
        """
        bad_pass_resp = client.post(
            LOGIN_URL,
            json={"email": VALID_USER["email"], "password": "WrongPass!"},
        )
        ghost_resp = client.post(
            LOGIN_URL,
            json={"email": "ghost@example.com", "password": "WrongPass!"},
        )
        assert bad_pass_resp.json()["detail"] == ghost_resp.json()["detail"]

    def test_login_invalid_email_format_returns_422(self, client):
        """An invalid email format in the login payload must return 422."""
        response = client.post(
            LOGIN_URL,
            json={"email": "not-an-email", "password": "SomePass1!"},
        )
        assert response.status_code == 422


# ===========================================================================
# POST /auth/login/form  (OAuth2 form data)
# ===========================================================================

class TestLoginForm:
    def test_form_login_success(self, client, registered_user):
        """OAuth2 form login (Swagger UI) must return a valid token."""
        response = client.post(
            LOGIN_FORM_URL,
            data={
                "username": VALID_USER["email"],
                "password": VALID_USER["password"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_form_login_wrong_credentials_returns_401(self, client, registered_user):
        """OAuth2 form login with wrong password must return 401."""
        response = client.post(
            LOGIN_FORM_URL,
            data={
                "username": VALID_USER["email"],
                "password": "BadPassword!",
            },
        )
        assert response.status_code == 401


# ===========================================================================
# GET /auth/me
# ===========================================================================

class TestGetMe:
    def test_get_me_success(self, client, auth_headers, registered_user):
        """An authenticated request must return the current user's profile."""
        response = client.get(ME_URL, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == VALID_USER["email"]
        assert data["full_name"] == VALID_USER["full_name"]
        assert "hashed_password" not in data

    def test_get_me_without_token_returns_401(self, client):
        """Calling /me without an Authorization header must return 401."""
        response = client.get(ME_URL)
        assert response.status_code == 401

    def test_get_me_invalid_token_returns_401(self, client):
        """A tampered/invalid token must return 401."""
        response = client.get(ME_URL, headers={"Authorization": "Bearer invalidtoken"})
        assert response.status_code == 401

    def test_get_me_malformed_header_returns_401(self, client):
        """A header without 'Bearer' prefix must return 401 or 403."""
        response = client.get(ME_URL, headers={"Authorization": "Token abc123"})
        assert response.status_code in (401, 403)

    def test_get_me_token_is_functional_after_register_and_login(
        self, client, registered_user
    ):
        """Full end-to-end: register → login → /me should return consistent data."""
        # Login to get a fresh token
        login_resp = client.post(
            LOGIN_URL,
            json={"email": VALID_USER["email"], "password": VALID_USER["password"]},
        )
        token = login_resp.json()["access_token"]

        # Call /me with the fresh token
        me_resp = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == VALID_USER["email"]


# ===========================================================================
# Security utilities
# ===========================================================================

class TestSecurityUtils:
    def test_password_hash_and_verify(self):
        """Hash should verify correctly and not equal the plain text."""
        from app.core.security import get_password_hash, verify_password

        plain = "MyS3cur3P@ss!"
        hashed = get_password_hash(plain)
        assert hashed != plain
        assert verify_password(plain, hashed) is True
        assert verify_password("WrongPass", hashed) is False

    def test_create_and_decode_token(self):
        """A freshly created token should decode to the correct sub claim."""
        from app.core.security import create_access_token, decode_token

        token = create_access_token(data={"sub": "42"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "42"

    def test_decode_tampered_token_returns_none(self):
        """A tampered token string should return None on decode."""
        from app.core.security import decode_token

        payload = decode_token("this.is.not.a.real.jwt")
        assert payload is None

    def test_expired_token_returns_none(self):
        """An already-expired token should decode to None."""
        from datetime import timedelta
        from app.core.security import create_access_token, decode_token

        token = create_access_token(
            data={"sub": "1"},
            expires_delta=timedelta(seconds=-1),  # already expired
        )
        payload = decode_token(token)
        assert payload is None

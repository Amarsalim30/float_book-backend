"""
Shared pytest fixtures and test configuration for the FloatBook backend.

Uses an in-memory SQLite database so tests run fast without needing Postgres.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app

# ---------------------------------------------------------------------------
# In-memory SQLite test database
# ---------------------------------------------------------------------------
SQLALCHEMY_TEST_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function", autouse=False)
def test_db():
    """
    Create all tables before each test and drop them afterward.
    Yields a test database session.
    """
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db):
    """
    FastAPI TestClient with the database dependency overridden
    to use the in-memory SQLite test database.
    """
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

VALID_USER = {
    "email": "test@example.com",
    "password": "SecurePass123",
    "full_name": "Test User",
}


@pytest.fixture
def registered_user(client):
    """Register a test user and return the response JSON."""
    response = client.post("/api/v1/auth/register", json=VALID_USER)
    assert response.status_code == 201, response.json()
    return response.json()


@pytest.fixture
def auth_token(client, registered_user):
    """Return a valid JWT access token for the registered test user."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": VALID_USER["email"], "password": VALID_USER["password"]},
    )
    assert response.status_code == 200, response.json()
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    """Return authorization headers with the test user's JWT."""
    return {"Authorization": f"Bearer {auth_token}"}

"""Pytest fixtures for API tests."""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# Ensure test env uses test DB if available
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/restaurant_training")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("BOOTSTRAP_SUPERADMIN_EMAIL", "owner@example.com")
os.environ.setdefault("BOOTSTRAP_SUPERADMIN_PASSWORD", "change_me_please")

from app.main import app


def _db_available() -> bool:
    """Check if database is reachable."""
    try:
        url = os.environ.get("DATABASE_URL", "")
        eng = create_engine(url)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        eng.dispose()
        return True
    except OperationalError:
        return False


@pytest.fixture
def client() -> TestClient:
    if not _db_available():
        pytest.skip("Database unavailable. Run: docker compose up -d")
    return TestClient(app)


@pytest.fixture
def auth_headers(client: TestClient) -> dict:
    """Login as superadmin and return Authorization header."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"login": "owner@example.com", "password": "change_me_please"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

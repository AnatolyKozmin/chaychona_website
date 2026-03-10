"""Auth API tests."""
from fastapi.testclient import TestClient


def test_login_success(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"login": "owner@example.com", "password": "change_me_please"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert len(data["access_token"]) > 0


def test_login_wrong_password(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"login": "owner@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_login_nonexistent_user(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"login": "nonexistent@example.com", "password": "any"},
    )
    assert resp.status_code == 401

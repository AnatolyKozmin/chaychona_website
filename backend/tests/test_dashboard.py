"""Dashboard API tests."""
from fastapi.testclient import TestClient


def test_dashboard_overview_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/dashboard/overview")
    assert resp.status_code == 401


def test_dashboard_overview_admin_ok(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/dashboard/overview", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "tests_created_total" in data
    assert "products_total" in data
    assert "attempts_day" in data
    assert "attempts_week" in data
    assert "attempts_month" in data
    assert "products_by_bucket" in data
    assert "restaurants" in data
    assert "top_results" in data


def test_dashboard_me_overview_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/v1/dashboard/me-overview")
    assert resp.status_code == 401


def test_dashboard_me_overview_authenticated_ok(client: TestClient, auth_headers: dict) -> None:
    resp = client.get("/api/v1/dashboard/me-overview", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_trainings" in data
    assert "completed_trainings" in data
    assert "completed_percent" in data
    assert "total_tests" in data
    assert "attempts_count" in data
    assert "best_result" in data
    assert "worst_result" in data
    assert "attempts_last_7_days" in data
    assert "avg_score_last_7_days" in data
    assert "current_streak_days" in data
    assert "longest_streak_days" in data
    assert "daily_progress" in data

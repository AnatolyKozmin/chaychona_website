"""Архив, удаление и сброс пароля сотрудников.

Уволенных нужно убирать из общего списка, но их результаты — это история
ресторана: удаление стёрло бы её из аналитики. Поэтому уволенных архивируют,
а удаляются только пустые аккаунты и дубли.
"""
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.quiz import QuizAttempt


@pytest.fixture
def employee(client: TestClient, auth_headers: dict) -> dict:
    """Свежий сотрудник: зарегистрировался сам, результатов пока нет."""
    marker = uuid.uuid4().hex[:8]
    restaurant = client.post(
        "/api/v1/users/catalog/restaurants", json={"name": f"__pytest_archive_{marker}"}, headers=auth_headers
    )
    assert restaurant.status_code == 201, restaurant.text
    job = client.post(
        "/api/v1/users/catalog/job-titles",
        json={"name": "Официант", "restaurant_id": restaurant.json()["id"]},
        headers=auth_headers,
    )
    assert job.status_code == 201, job.text
    login = f"emp{marker}"
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Мария",
            "last_name": "Иванова",
            "restaurant": restaurant.json()["name"],
            "job_title": "Официант",
            "desired_login": login,
            "password": "пароль1",
        },
    )
    assert registered.status_code == 201, registered.text
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers).json()
    return {"id": me["id"], "login": login, "password": "пароль1", "headers": headers}


def _login(client: TestClient, login: str, password: str):
    return client.post("/api/v1/auth/login", json={"login": login, "password": password})


def test_archived_employee_cannot_log_in_and_can_be_restored(client, auth_headers, employee):
    archived = client.patch(
        f"/api/v1/users/{employee['id']}/active", json={"is_active": False}, headers=auth_headers
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["is_active"] is False
    assert _login(client, employee["login"], employee["password"]).status_code == 401

    restored = client.patch(
        f"/api/v1/users/{employee['id']}/active", json={"is_active": True}, headers=auth_headers
    )
    assert restored.status_code == 200
    assert _login(client, employee["login"], employee["password"]).status_code == 200


def test_employee_without_results_can_be_deleted(client, auth_headers, employee):
    resp = client.delete(f"/api/v1/users/{employee['id']}", headers=auth_headers)

    assert resp.status_code == 204, resp.text
    assert _login(client, employee["login"], employee["password"]).status_code == 401


def test_employee_with_test_results_is_archived_not_deleted(client, auth_headers, employee):
    """Результаты — история ресторана: удалить такого нельзя, только в архив."""
    marker = uuid.uuid4().hex[:8]
    restaurant = client.post(
        "/api/v1/users/catalog/restaurants", json={"name": f"__pytest_hist_{marker}"}, headers=auth_headers
    ).json()
    job = client.post(
        "/api/v1/users/catalog/job-titles",
        json={"name": f"__job_{marker}", "restaurant_id": restaurant["id"]},
        headers=auth_headers,
    ).json()
    test_id = client.post(
        "/api/v1/tests",
        json={
            "title": f"История {marker}",
            "restaurant_id": restaurant["id"],
            "job_title_id": job["id"],
            "questions": [
                {
                    "text": "Вопрос",
                    "question_type": "single",
                    "options": [{"text": "да", "is_correct": True}, {"text": "нет", "is_correct": False}],
                }
            ],
        },
        headers=auth_headers,
    ).json()["id"]
    # Попытку пишем напрямую: удалению важен сам факт результата, а не то,
    # как сотрудник до него дошёл.
    with SessionLocal() as db:
        db.add(
            QuizAttempt(
                test_id=test_id,
                user_id=uuid.UUID(employee["id"]),
                finished_at=datetime.utcnow(),
                total_questions=1,
                correct_answers=1,
                incorrect_answers=0,
            )
        )
        db.commit()

    resp = client.delete(f"/api/v1/users/{employee['id']}", headers=auth_headers)

    assert resp.status_code == 409
    assert "архив" in resp.json()["detail"]


def test_reset_password_gives_a_working_temporary_password(client, auth_headers, employee):
    resp = client.post(f"/api/v1/users/{employee['id']}/reset-password", headers=auth_headers)

    assert resp.status_code == 200, resp.text
    temporary = resp.json()["temporary_password"]
    assert len(temporary) == 8
    # Похожие символы диктовать голосом нельзя — их в пароле быть не должно.
    assert not set(temporary) & set("l1IO0o")
    assert _login(client, employee["login"], employee["password"]).status_code == 401
    assert _login(client, employee["login"], temporary).status_code == 200


def test_learner_cannot_archive_anyone(client, employee, auth_headers):
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()

    resp = client.patch(f"/api/v1/users/{me['id']}/active", json={"is_active": False}, headers=employee["headers"])

    assert resp.status_code == 403


def test_nobody_can_archive_themselves(client, auth_headers):
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()

    resp = client.patch(f"/api/v1/users/{me['id']}/active", json={"is_active": False}, headers=auth_headers)

    assert resp.status_code == 400

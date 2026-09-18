"""Повторная отправка теста с телефона не плодит попытки и не теряет результат.

В проде тест терялся так: сотрудник жмёт «Завершить», связь в зале рвётся,
ответ сервера не доходит, человек жмёт ещё раз. Первая отправка к этому моменту
могла уже записаться. Телефон присылает номер попытки, выданный при старте, и
повтор с тем же номером должен вернуть ту же попытку, а не создать вторую.
"""
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def quiz(client: TestClient, auth_headers: dict) -> dict:
    marker = uuid.uuid4().hex[:8]
    restaurant = client.post(
        "/api/v1/users/catalog/restaurants",
        json={"name": f"__pytest_retry_{marker}"},
        headers=auth_headers,
    )
    assert restaurant.status_code == 201, restaurant.text
    job = client.post(
        "/api/v1/users/catalog/job-titles",
        json={"restaurant_id": restaurant.json()["id"], "name": f"__pytest_job_{marker}"},
        headers=auth_headers,
    )
    assert job.status_code == 201, job.text
    created = client.post(
        "/api/v1/tests",
        json={
            "title": f"Повтор отправки {marker}",
            "restaurant_id": restaurant.json()["id"],
            "job_title_id": job.json()["id"],
            "questions": [
                {
                    "text": "Сколько минут жарится самса?",
                    "question_type": "single",
                    "options": [
                        {"text": "20", "is_correct": True},
                        {"text": "5", "is_correct": False},
                    ],
                }
            ],
        },
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    test_id = created.json()["id"]
    taken = client.get(f"/api/v1/tests/{test_id}/take", headers=auth_headers).json()
    question = taken["questions"][0]
    correct = next(option["id"] for option in question["options"] if option["text"] == "20")
    return {"test_id": test_id, "question_id": question["id"], "correct_option_id": correct}


def _submit(client, auth_headers, quiz, client_attempt_id):
    return client.post(
        f"/api/v1/tests/{quiz['test_id']}/submit",
        json={
            "answers": [{"question_id": quiz["question_id"], "option_ids": [quiz["correct_option_id"]]}],
            "client_attempt_id": client_attempt_id,
        },
        headers=auth_headers,
    )


def _attempts_of(client, auth_headers, test_id) -> list:
    attempts = client.get("/api/v1/tests/my-attempts", headers=auth_headers).json()
    return [attempt for attempt in attempts if attempt["test_id"] == test_id]


def test_retry_with_the_same_attempt_id_returns_the_first_result(client, auth_headers, quiz):
    attempt_key = uuid.uuid4().hex

    first = _submit(client, auth_headers, quiz, attempt_key)
    retry = _submit(client, auth_headers, quiz, attempt_key)

    assert first.status_code == 200, first.text
    assert retry.status_code == 200, retry.text
    assert retry.json()["attempt_id"] == first.json()["attempt_id"]
    assert retry.json()["correct_answers"] == 1
    # Разбор ответов на экране результата должен совпасть с первой отправкой.
    assert retry.json()["results"][0]["selected_options"] == ["20"]
    assert retry.json()["results"][0]["is_correct"] is True
    assert len(_attempts_of(client, auth_headers, quiz["test_id"])) == 1


def test_new_attempt_id_means_a_new_attempt(client, auth_headers, quiz):
    """Пересдача — это новый номер: вторая попытка должна записаться."""
    assert _submit(client, auth_headers, quiz, uuid.uuid4().hex).status_code == 200
    assert _submit(client, auth_headers, quiz, uuid.uuid4().hex).status_code == 200

    assert len(_attempts_of(client, auth_headers, quiz["test_id"])) == 2


def test_old_clients_without_attempt_id_still_submit(client, auth_headers, quiz):
    """Телефоны со старой версией страницы номер не шлют — отправка обязана работать."""
    resp = client.post(
        f"/api/v1/tests/{quiz['test_id']}/submit",
        json={"answers": [{"question_id": quiz["question_id"], "option_ids": [quiz["correct_option_id"]]}]},
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text

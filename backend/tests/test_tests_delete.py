"""Регрессия: удаление теста, у которого есть попытки с ответами.

Ловит порядок DELETE между quiz_attempt_answers и quiz_attempts —
без явных bulk-DELETE SQLAlchemy мог удалить попытки раньше ответов
и упасть на внешнем ключе (только на Postgres, SQLite это не ловит).
"""
import os
import uuid

from sqlalchemy import create_engine, text


def test_delete_test_with_attempts_and_answers(client, auth_headers):
    marker = uuid.uuid4().hex[:8]

    resto = client.post(
        "/api/v1/users/catalog/restaurants",
        json={"name": f"__pytest_resto_{marker}"},
        headers=auth_headers,
    )
    assert resto.status_code == 201, resto.text
    restaurant_id = resto.json()["id"]

    job = client.post(
        "/api/v1/users/catalog/job-titles",
        json={"restaurant_id": restaurant_id, "name": f"__pytest_job_{marker}"},
        headers=auth_headers,
    )
    assert job.status_code == 201, job.text
    job_title_id = job.json()["id"]

    try:
        created = client.post(
            "/api/v1/tests",
            json={
                "title": f"Тест на удаление {marker}",
                "restaurant_id": restaurant_id,
                "job_title_id": job_title_id,
                "questions": [
                    {
                        "text": "2+2?",
                        "question_type": "single",
                        "options": [
                            {"text": "4", "is_correct": True},
                            {"text": "5", "is_correct": False},
                        ],
                    }
                ],
            },
            headers=auth_headers,
        )
        assert created.status_code == 201, created.text
        test_id = created.json()["id"]

        # Попытка с ответом — вставляем напрямую, как их пишет прохождение теста.
        engine = create_engine(os.environ["DATABASE_URL"])
        with engine.begin() as conn:
            user_id = conn.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": "owner@example.com"},
            ).scalar_one()
            attempt_id = conn.execute(
                text(
                    """
                    INSERT INTO quiz_attempts
                        (test_id, user_id, finished_at, total_questions, correct_answers, incorrect_answers, created_at)
                    VALUES (:test_id, :user_id, NOW(), 1, 1, 0, NOW())
                    RETURNING id
                    """
                ),
                {"test_id": test_id, "user_id": user_id},
            ).scalar_one()
            conn.execute(
                text(
                    """
                    INSERT INTO quiz_attempt_answers
                        (attempt_id, question_text, selected_option_ids, selected_options_text,
                         correct_option_ids, correct_options_text, is_correct)
                    VALUES (:attempt_id, '2+2?', '', '4', '', '4', TRUE)
                    """
                ),
                {"attempt_id": attempt_id},
            )

        resp = client.delete(f"/api/v1/tests/{test_id}", headers=auth_headers)
        assert resp.status_code == 204, resp.text

        with engine.connect() as conn:
            leftover_attempts = conn.execute(
                text("SELECT count(*) FROM quiz_attempts WHERE test_id = :test_id"),
                {"test_id": test_id},
            ).scalar_one()
            leftover_answers = conn.execute(
                text("SELECT count(*) FROM quiz_attempt_answers WHERE attempt_id = :attempt_id"),
                {"attempt_id": attempt_id},
            ).scalar_one()
        engine.dispose()
        assert leftover_attempts == 0
        assert leftover_answers == 0

        assert client.get("/api/v1/tests", headers=auth_headers).status_code == 200
    finally:
        client.delete(f"/api/v1/users/catalog/job-titles/{job_title_id}", headers=auth_headers)
        client.delete(f"/api/v1/users/catalog/restaurants/{restaurant_id}", headers=auth_headers)

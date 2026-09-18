"""Самостоятельная регистрация сотрудников и вход с телефона.

Что здесь закреплено и почему:

- регистрация сразу даёт рабочий аккаунт — раньше каждую заявку одобрял
  суперадмин, и новые сотрудники днями не могли войти;
- пробел в конце логина и заглавная первая буква не мешают входу — так
  набирает логин клавиатура телефона;
- заявка, поданная до перехода и так и не одобренная, превращается в аккаунт
  при первом входе с верным паролем, а не отвечает «неверный пароль».
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import RegistrationRequest, RegistrationRequestStatus, User


@pytest.fixture
def catalog(client: TestClient, auth_headers: dict) -> dict:
    """Свой ресторан и должность на каждый тест — чтобы тесты не делили данные."""
    suffix = uuid.uuid4().hex[:8]
    restaurant = client.post(
        "/api/v1/users/catalog/restaurants",
        json={"name": f"Тестовая точка {suffix}"},
        headers=auth_headers,
    )
    assert restaurant.status_code == 201, restaurant.text
    job_title = client.post(
        "/api/v1/users/catalog/job-titles",
        json={"name": "Официант", "restaurant_id": restaurant.json()["id"]},
        headers=auth_headers,
    )
    assert job_title.status_code == 201, job_title.text
    return {"restaurant": restaurant.json()["name"], "job_title": "Официант"}


def _register(client: TestClient, catalog: dict, login: str, password: str = "чайхона1"):
    return client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Анна",
            "last_name": "Петрова",
            "restaurant": catalog["restaurant"],
            "job_title": catalog["job_title"],
            "desired_login": login,
            "password": password,
        },
    )


def _login(client: TestClient, login: str, password: str):
    return client.post("/api/v1/auth/login", json={"login": login, "password": password})


def test_registration_gives_a_working_account_without_approval(client, catalog):
    login = f"anna{uuid.uuid4().hex[:6]}"

    resp = _register(client, catalog, login)

    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == login
    assert me.json()["role"] == "learner"
    assert me.json()["restaurant"] == catalog["restaurant"]
    assert me.json()["job_title"] == catalog["job_title"]


def test_phone_keyboard_quirks_do_not_break_login(client, catalog):
    """Пробел после слова и заглавная первая буква — это телефон, а не другой логин."""
    login = f"ivan{uuid.uuid4().hex[:6]}"
    assert _register(client, catalog, f" {login.capitalize()} ").status_code == 201

    assert _login(client, f"{login.capitalize()} ", "чайхона1").status_code == 200


def test_cyrillic_short_password_is_accepted(client, catalog):
    """Шесть символов по-русски — нормальный пароль для сотрудника в зале."""
    login = f"olga{uuid.uuid4().hex[:6]}"
    assert _register(client, catalog, login, password="чайник").status_code == 201
    assert _login(client, login, "чайник").status_code == 200


def test_password_shorter_than_six_is_rejected(client, catalog):
    resp = _register(client, catalog, f"short{uuid.uuid4().hex[:6]}", password="12345")
    assert resp.status_code == 422


def test_taken_login_is_explained(client, catalog):
    login = f"dup{uuid.uuid4().hex[:6]}"
    assert _register(client, catalog, login).status_code == 201

    resp = _register(client, catalog, login)

    assert resp.status_code == 400
    assert "занят" in resp.json()["detail"]


def test_unknown_restaurant_is_explained(client, catalog):
    resp = _register(client, {**catalog, "restaurant": "Несуществующая точка"}, f"x{uuid.uuid4().hex[:6]}")
    assert resp.status_code == 400
    assert "ресторан" in resp.json()["detail"].lower()


def test_old_pending_request_turns_into_account_on_first_login(client, catalog):
    """Заявку подали до самостоятельной регистрации и не одобрили — вход её «одобряет»."""
    login = f"old{uuid.uuid4().hex[:6]}"
    with SessionLocal() as db:
        db.add(
            RegistrationRequest(
                first_name="Пётр",
                last_name="Сидоров",
                restaurant=catalog["restaurant"],
                desired_job_title=catalog["job_title"],
                desired_login=login,
                desired_password_hash=get_password_hash("старыйпароль"),
                status=RegistrationRequestStatus.PENDING,
            )
        )
        db.commit()

    assert _login(client, login, "неверный").status_code == 401
    assert _login(client, login, "старыйпароль").status_code == 200

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == login).one()
        assert user.restaurant == catalog["restaurant"]
        request = db.query(RegistrationRequest).filter(RegistrationRequest.desired_login == login).one()
        assert request.status == RegistrationRequestStatus.APPROVED

# Restaurant Training Platform (MVP)

Initial scaffold for staff training web app:
- Backend: FastAPI + PostgreSQL + SQLAlchemy + Pydantic
- Frontend: Vue 3 + Vite + Pinia + Vue Router

## Role model

Three access levels are implemented:
- `superadmin` - full control, can change any user's role
- `admin` - operational access, can view users and update learner job titles
- `learner` - studies courses/tests (same access level for waiter, bartender, etc.)

`learner` has a separate field `job_title` to separate content tracks while keeping one permission level.

## JWT auth

Implemented token flow:
- Access token (short lifetime)
- Refresh token (long lifetime)
- Login, refresh, and current-user endpoints

Backend endpoints:
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `GET /api/v1/auth/me`
- `GET /api/v1/users` (admin/superadmin)
- `POST /api/v1/users` (superadmin, create user directly)
- `PATCH /api/v1/users/{user_id}/role` (superadmin)
- `PATCH /api/v1/users/{user_id}/job-title` (admin/superadmin, learners only)
- `GET /api/v1/users/registration-requests` (superadmin)
- `POST /api/v1/users/registration-requests/{request_id}/approve` (superadmin)
- `POST /api/v1/users/registration-requests/{request_id}/reject` (superadmin)

Registration flow:
- User submits access request via `POST /api/v1/auth/register` with `first_name`, `last_name`, `restaurant`, `job_title`, `desired_login`, `password`
- Superadmin reviews request in Users page and approves/rejects it
- Approved request creates learner account; then user can login

## Dishes content import

Import script for Telegram export:
- Script: `backend/scripts/import_dishes_content.py`
- Schema notes: `backend/docs/dishes_import_schema.md`

When running with Docker, execute import inside `backend` container (recommended):

```bash
docker compose exec backend python scripts/import_dishes_content.py \
  --export-root "/import/content_export" \
  --dry-run \
  --verbose
```

Run actual import:

```bash
docker compose exec backend python scripts/import_dishes_content.py \
  --export-root "/import/content_export" \
  --verbose
```

Local Python run (if backend deps installed in your venv):

```bash
python3 backend/scripts/import_dishes_content.py \
  --export-root "/Users/anatolij/work/first_bot/app_from_container/content_export" \
  --dry-run \
  --verbose
```

## Run in Docker (recommended)

```bash
docker compose up --build
```

Services:
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`

To stop and remove volumes:

```bash
docker compose down -v
```

## Local run (without Docker)

### 1) Database

```bash
docker compose up -d
```

### 2) Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

At startup backend creates tables and bootstraps initial `superadmin` from `.env`.

### 3) Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend starts on `http://localhost:5173`.

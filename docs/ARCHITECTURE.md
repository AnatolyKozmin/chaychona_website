# Архитектура проекта

Веб-платформа для обучения персонала ресторанной сети «Чайхона №1» (см. бутстрап в [backend/app/main.py](../backend/app/main.py) — сидируется ресторан «Чайхона №1» при первом старте). Сотрудники проходят курсы/тесты/чек-листы смен, администраторы управляют контентом и доступом.

Стек: **FastAPI + PostgreSQL + SQLAlchemy** (backend) / **Vue 3 + Vite + Pinia + Vue Router + TS** (frontend), деплой через Docker Compose.

## Структура репозитория

```
backend/app/
  api/v1/        — роуты (auth, users, courses, tests, checklists, menu, dashboard)
  models/        — SQLAlchemy-модели (user, course, quiz, menu, checklist)
  schemas/       — Pydantic-схемы запросов/ответов
  core/          — config.py (Settings из .env), security.py (хэши паролей, JWT)
  db/            — session.py (engine/SessionLocal), base.py (Base)
  word_tests_import.py — парсер .docx для импорта тестов
  main.py        — точка входа, CORS, lifespan-миграции (raw SQL ALTER/CREATE), include_router, /health
backend/scripts/import_dishes_content.py — импорт блюд из Telegram-экспорта
backend/tests/   — pytest (health, auth, dashboard, word-импорт тестов)

frontend/src/
  api/client.ts   — axios-инстанс, авто-refresh access token по 401
  stores/auth.ts  — Pinia store: login/register/refresh/logout, роли isAdmin/isSuperadmin
  router/index.ts — роуты + guard (redirect на /login если не авторизован)
  views/          — страницы (см. таблицу ниже)

docs/word_tests_format.md — формат .docx для импорта тестов
templates/tests_import_template.xlsx — шаблон Excel-импорта тестов
docker-compose.yml        — прод-профиль (порты 80/8000, внешний VITE_API_BASE_URL прописан в build args)
docker-compose.local.yml  — dev-профиль (hot reload, Vite на 5173, Postgres наружу на 5432)
```

Файлы в корне `=`, `reading`, `resolve`, `transferring`, `backup.dump`, `тесты по санитарии (1).docx` — случайные артефакты первого коммита («Initial app state before server migration»), не относятся к коду приложения.

## Роли и доступ

Три уровня роли (`backend/app/models/user.py`):
- `superadmin` — полный контроль, управление ролями
- `admin` — операционный доступ: видит пользователей, меняет `job_title` у learner'ов
- `learner` — проходит курсы/тесты/чек-листы; поле `job_title` отделяет контент-трек (официант/бармен/...) без смены уровня доступа

Регистрация — заявочная: `POST /auth/register` создаёт `RegistrationRequest` (pending), superadmin одобряет/отклоняет (`/users/registration-requests/...`) → при approve создаётся `User` с ролью `learner`.

JWT: access (короткий) + refresh (длинный) токен, `frontend/src/api/client.ts` автоматически дёргает `/auth/refresh` при 401 и повторяет запрос.

## Доменная модель

| Модель | Файл | Суть |
|---|---|---|
| `User`, `RegistrationRequest`, `RestaurantCatalog`, `JobTitleCatalog` | `models/user.py` | пользователи, заявки на доступ, справочники ресторанов/должностей |
| `Course`, `CourseBlock`, `CourseSubBlock`, `CourseBlockProgress` | `models/course.py` | учебные курсы (блоки текста+картинок), привязка к ресторану/должности, прогресс прохождения по блокам |
| `QuizTest`, `QuizQuestion`, `QuizOption`, `QuizAttempt`, `QuizAttemptAnswer` | `models/quiz.py` | тесты (single/multiple choice), попытки прохождения с детальным разбором ответов |
| `MenuBranch`, `MenuCategory`, `MenuDish` | `models/menu.py` | меню ресторана: категории, блюда (фото/аудио/видео/ингредиенты/цена) — раздел «Вкусная тетрадь» |
| `ShiftType`, `Checklist`, `ChecklistItem`, `ChecklistCompletion`, `ChecklistItemCompletion` | `models/checklist.py` | чек-листы смен (открытие/закрытие), пункты с опциональным фото-подтверждением |

`Course`, `QuizTest`, `Checklist` все опционально/обязательно привязаны к `restaurant_id` + `job_title_id` — так контент таргетируется на конкретную должность в конкретном ресторане. `Course.linked_test_id` связывает курс с финальным тестом.

## API (backend/app/api/v1, префикс `/api/v1`)

- **auth.py** — `register`, `login`, `refresh`, `me`
- **users.py** — список/активность пользователей, смена роли/job-title/learner-profile, создание юзера, обработка заявок на регистрацию, справочники ресторанов/должностей (`/catalog/...`)
- **courses.py** — CRUD курсов (`/admin`), для learner: `/my`, `/my-overview`, прохождение блоков (`/my/{id}/study`, `/my/{id}/blocks/{id}/complete`)
- **tests.py** — CRUD тестов, прохождение (`/my`, `/{id}/take`, `/{id}/submit`), история попыток (`/my-attempts`), аналитика (`/analytics`), импорт из Excel/Word (`/import-xlsx`, `/import-docx`, `/parse-docx`, `/import-apply`, `/import-template`)
- **checklists.py** — типы смен, CRUD чек-листов, прохождение (`/my`, `/my/{id}/complete`), журнал прохождений (`/admin/completions`), загрузка фото (`/media`)
- **menu.py** — публичная лента меню (`/feed`, `/categories`), admin CRUD по branches/categories/dishes, загрузка медиа
- **dashboard.py** — `/overview` (admin-сводка), `/me-overview` (сводка для learner'а)
- доп. в `main.py`: `GET /health`, `GET /api/v1/menu/media?path=...` (раздача файлов из `CONTENT_EXPORT_ROOT` или `backend/media_uploads`)

Полный список путей с сигнатурами — смотри Swagger на `/docs` при запущенном backend, либо grep `@router\.` в `backend/app/api/v1/`.

## Frontend-страницы (frontend/src/views, маппинг в router/index.ts)

| Роут | Компонент | Назначение |
|---|---|---|
| `/login` | LoginView | вход/регистрация заявки |
| `/` | DashboardView | дашборд (своя сводка под роль) |
| `/standards`, `/standards/:id` | StandardsView / StandardsStudyView | список курсов / прохождение курса |
| `/my-tests` | MyTestsView | тесты learner'а |
| `/my-checklists` | MyChecklistsView | чек-листы learner'а |
| `/statistics` | StatisticsView | статистика (admin) |
| `/tests-analytics` | TestsAnalyticsView | аналитика по тестам |
| `/tasty-notebook` | TastyNotebookView | «Вкусная тетрадь» — меню/блюда |
| `/tests` | TestsAdminView | конструктор тестов (создание, импорт Word/Excel) |
| `/checklists` | ChecklistsAdminView | конструктор чек-листов |
| `/users/access` | UsersAccessView | заявки на регистрацию |
| `/users/people` | UsersPeopleView | управление пользователями/ролями |

Router guard (`router/index.ts`): неавторизованных редиректит на `/login`; авторизованных с `/login` — на дашборд. Авторизация определяется по наличию `access_token` в `localStorage`.

## Конфигурация и окружение

`backend/.env.example` → переменные (`backend/app/core/config.py`):
- `DATABASE_URL` — `postgresql+psycopg2://...`
- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`
- `BOOTSTRAP_SUPERADMIN_EMAIL`, `BOOTSTRAP_SUPERADMIN_PASSWORD` — на старте создаётся/обновляется superadmin с этими данными ([main.py](../backend/app/main.py) `_run_startup`)
- `CONTENT_EXPORT_ROOT` — путь к экспорту контента (для медиа и скрипта импорта блюд)

При старте (`lifespan` в `main.py`) выполняются `Base.metadata.create_all` + ряд idempotent `ALTER/CREATE` миграций «на лету» (raw SQL) — **в проекте нет Alembic**, схема эволюционирует прямыми SQL-патчами в `_run_startup`. При добавлении новых колонок/таблиц следующий разработчик должен дописывать миграцию туда же.

Frontend: `VITE_API_BASE_URL` (build-time для прод-докера, runtime env для local-докера), по умолчанию `http://localhost:8000/api/v1`.

## Запуск

См. [README.md](../README.md) — там подробные команды для:
- прод-профиля (`docker compose up --build`: frontend :80, backend :8000)
- local dev-профиля (`docker-compose.local.yml`: Vite :5173, backend :8000, Postgres :5432 наружу)
- запуска без Docker (venv + uvicorn, npm run dev)
- тестов (`pytest tests/ -v` в backend, требует Postgres; `npm run test` во frontend — Vitest)

## Импорт контента

- **Блюда**: `backend/scripts/import_dishes_content.py` — импорт из экспорта Telegram-бота, схема описана в `backend/docs/dishes_import_schema.md`. Запуск: `docker compose exec backend python scripts/import_dishes_content.py --export-root ... [--dry-run] --verbose`.
- **Тесты**: импорт из `.docx` (формат — [docs/word_tests_format.md](word_tests_format.md): вопросы вида `1. текст`, варианты `A)`/`а)`, верный ответ выделен **жирным**; несколько жирных вариантов → тип `multiple`) или из Excel по шаблону `templates/tests_import_template.xlsx`. UI — раздел «Конструктор тестов» (`/tests`), backend — `tests.py` (`/parse-docx` → превью, `/import-apply` → применение; `/import-xlsx` — прямой импорт Excel).

## Известные особенности (важно учитывать при изменениях)

- Нет Alembic — миграции схемы это код в `main.py::_run_startup`, выполняется на каждом старте backend.
- CORS открыт на `allow_origins=["*"]` — учитывать при работе с авторизацией/cookies.
- Медиа-файлы (фото блюд, фото подтверждения чек-листов) раздаются через `/api/v1/menu/media?path=...` с поиском по двум корням (`CONTENT_EXPORT_ROOT`, затем `backend/media_uploads`), путь нормализуется и проверяется на выход за пределы root.
- `docker-compose.yml` зашивает внешний IP `194.87.140.241` в build-arg `VITE_API_BASE_URL` для прод-фронтенда — при смене сервера это нужно поменять.

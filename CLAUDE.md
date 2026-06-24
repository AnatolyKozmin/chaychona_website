# CLAUDE.md

Платформа обучения персонала ресторанной сети «Чайхона №1»: курсы, тесты, чек-листы смен, меню («Вкусная тетрадь»), управление пользователями/ролями.

Стек: FastAPI + PostgreSQL + SQLAlchemy (backend/) / Vue 3 + Vite + Pinia + Vue Router + TS (frontend/). Деплой — Docker Compose.

Подробная архитектура (модели, API-роуты, frontend-страницы, конфиг, особенности): см. **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.
Запуск/тесты/команды: см. **[README.md](README.md)**.
Формат импорта тестов из Word: **[docs/word_tests_format.md](docs/word_tests_format.md)**.

## Быстрые факты, которые легко упустить

- Нет Alembic — миграции схемы — это idempotent raw SQL в `backend/app/main.py::_run_startup`, выполняется при каждом старте backend. Новые изменения схемы дописывать туда же.
- Роли: `superadmin` / `admin` / `learner` (у learner отдельное поле `job_title` для трека контента). См. `backend/app/models/user.py`.
- Регистрация — заявочная (`registration_requests`), одобряет superadmin.
- JWT access+refresh, frontend (`frontend/src/api/client.ts`) авто-рефрешит токен по 401.
- Контент (курсы/тесты/чек-листы) таргетируется через `restaurant_id` + `job_title_id`.

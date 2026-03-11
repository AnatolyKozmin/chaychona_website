from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import select, text, update

from app.api.v1.auth import router as auth_router
from app.api.v1.checklists import router as checklists_router
from app.api.v1.courses import router as courses_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.menu import router as menu_router
from app.api.v1.tests import router as tests_router
from app.api.v1.users import router as users_router
from app.core.config import get_settings
from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.menu import MenuCategory, MenuDish
from app.models import checklist as _checklist_models  # noqa: F401
from app.models import course as _course_models  # noqa: F401
from app.models import menu as _menu_models  # noqa: F401
from app.models import quiz as _quiz_models  # noqa: F401
from app.models.checklist import ShiftType
from app.models.user import RestaurantCatalog, Role, User

settings = get_settings()


def _run_startup() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE registration_requests ADD COLUMN IF NOT EXISTS desired_job_title VARCHAR(255)")
        )
        connection.execute(text("ALTER TABLE job_title_catalog ADD COLUMN IF NOT EXISTS restaurant_id UUID"))
        connection.execute(
            text(
                "DO $$ "
                "BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'job_title_catalog_restaurant_id_fkey') THEN "
                "ALTER TABLE job_title_catalog "
                "ADD CONSTRAINT job_title_catalog_restaurant_id_fkey "
                "FOREIGN KEY (restaurant_id) REFERENCES restaurant_catalog (id); "
                "END IF; "
                "END $$;"
            )
        )
        connection.execute(text("DROP INDEX IF EXISTS ix_job_title_catalog_name"))
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_job_title_catalog_name "
                "ON job_title_catalog (name)"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_job_title_catalog_restaurant_name "
                "ON job_title_catalog (restaurant_id, lower(name)) "
                "WHERE restaurant_id IS NOT NULL"
            )
        )
        connection.execute(text("ALTER TABLE job_title_catalog DROP CONSTRAINT IF EXISTS job_title_catalog_name_key"))
        connection.execute(text("ALTER TABLE quiz_tests ADD COLUMN IF NOT EXISTS external_code VARCHAR(120)"))
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_quiz_tests_external_code "
                "ON quiz_tests (external_code) WHERE external_code IS NOT NULL"
            )
        )
        connection.execute(text("ALTER TABLE menu_dishes ADD COLUMN IF NOT EXISTS restaurant_id UUID"))
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS menu_branches ("
                "id SERIAL PRIMARY KEY, "
                "name VARCHAR(64) NOT NULL, "
                "is_active BOOLEAN NOT NULL DEFAULT TRUE, "
                "sort_order INTEGER NOT NULL DEFAULT 0, "
                "created_at TIMESTAMP NOT NULL DEFAULT NOW(), "
                "updated_at TIMESTAMP NOT NULL DEFAULT NOW()"
                ")"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_menu_branches_name_lower "
                "ON menu_branches (lower(name))"
            )
        )
        connection.execute(text("ALTER TABLE menu_branches ALTER COLUMN created_at SET DEFAULT NOW()"))
        connection.execute(text("ALTER TABLE menu_branches ALTER COLUMN updated_at SET DEFAULT NOW()"))
        connection.execute(text("ALTER TABLE menu_categories ADD COLUMN IF NOT EXISTS restaurant_id UUID"))
        connection.execute(text("ALTER TABLE menu_categories ADD COLUMN IF NOT EXISTS branch_id INTEGER"))
        connection.execute(
            text(
                "DO $$ "
                "BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'menu_categories_restaurant_id_fkey') THEN "
                "ALTER TABLE menu_categories "
                "ADD CONSTRAINT menu_categories_restaurant_id_fkey "
                "FOREIGN KEY (restaurant_id) REFERENCES restaurant_catalog (id); "
                "END IF; "
                "END $$;"
            )
        )
        connection.execute(
            text(
                "DO $$ "
                "BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'menu_categories_branch_id_fkey') THEN "
                "ALTER TABLE menu_categories "
                "ADD CONSTRAINT menu_categories_branch_id_fkey "
                "FOREIGN KEY (branch_id) REFERENCES menu_branches (id); "
                "END IF; "
                "END $$;"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_menu_categories_restaurant_id "
                "ON menu_categories (restaurant_id)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_menu_categories_branch_id "
                "ON menu_categories (branch_id)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO menu_branches (name, is_active, sort_order, created_at, updated_at) "
                "SELECT DISTINCT trim(menu_type), TRUE, 0, NOW(), NOW() "
                "FROM menu_categories "
                "WHERE menu_type IS NOT NULL AND trim(menu_type) <> '' "
                "ON CONFLICT DO NOTHING"
            )
        )
        connection.execute(
            text(
                "UPDATE menu_categories c "
                "SET branch_id = b.id "
                "FROM menu_branches b "
                "WHERE c.branch_id IS NULL "
                "AND c.menu_type IS NOT NULL "
                "AND trim(c.menu_type) <> '' "
                "AND lower(trim(c.menu_type)) = lower(b.name)"
            )
        )
        connection.execute(
            text(
                "DO $$ "
                "BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'menu_dishes_restaurant_id_fkey') THEN "
                "ALTER TABLE menu_dishes "
                "ADD CONSTRAINT menu_dishes_restaurant_id_fkey "
                "FOREIGN KEY (restaurant_id) REFERENCES restaurant_catalog (id); "
                "END IF; "
                "END $$;"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_menu_dishes_restaurant_id "
                "ON menu_dishes (restaurant_id)"
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_course_block_progress_user_course_block "
                "ON course_block_progress (user_id, course_id, block_id)"
            )
        )

    db = SessionLocal()
    try:
        email = settings.bootstrap_superadmin_email.lower()
        existing = db.scalar(select(User).where(User.email == email))
        if not existing:
            user = User(
                email=email,
                full_name="System Owner",
                password_hash=get_password_hash(settings.bootstrap_superadmin_password),
                role=Role.SUPERADMIN,
                is_active=True,
            )
            db.add(user)
            db.commit()
        else:
            # Keep bootstrap superadmin credentials in sync after hash scheme changes.
            existing.password_hash = get_password_hash(settings.bootstrap_superadmin_password)
            existing.role = Role.SUPERADMIN
            existing.is_active = True
            db.commit()

        chaihona = db.scalar(select(RestaurantCatalog).where(RestaurantCatalog.name == "Чайхона №1"))
        if not chaihona:
            chaihona = RestaurantCatalog(name="Чайхона №1")
            db.add(chaihona)
            db.flush()

        db.execute(
            update(MenuDish)
            .where(MenuDish.restaurant_id.is_(None))
            .values(restaurant_id=chaihona.id)
        )
        db.execute(
            update(MenuCategory)
            .where(MenuCategory.restaurant_id.is_(None))
            .values(restaurant_id=chaihona.id)
        )
        db.commit()

        # Seed shift types for checklists
        if db.scalar(select(ShiftType).limit(1)) is None:
            for name, order in [("Открытие смены", 0), ("Закрытие смены", 1)]:
                db.add(ShiftType(name=name, is_active=True, sort_order=order))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _run_startup()
    yield


app = FastAPI(title="Restaurant Training API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(checklists_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(menu_router, prefix="/api/v1")
app.include_router(tests_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(courses_router, prefix="/api/v1")


@app.get("/health")
def healthcheck():
    return {"status": "ok"}


@app.get("/api/v1/menu/media")
def get_menu_media(path: str = Query(..., min_length=1)):
    normalized_path = path.lstrip("/")
    roots: list[Path] = []
    if settings.content_export_root:
        roots.append(Path(settings.content_export_root).resolve())
    roots.append((Path(__file__).resolve().parents[1] / "media_uploads").resolve())

    for root in roots:
        candidate = (root / normalized_path).resolve()
        if not str(candidate).startswith(str(root)):
            continue
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)

    raise HTTPException(status_code=404, detail="Media file not found")

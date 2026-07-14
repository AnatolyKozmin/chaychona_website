import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.menu import MenuBranch, MenuCategory, MenuDish, MenuDishVideoJob
from app.models.user import RestaurantCatalog, Role, User
from app.schemas.menu import (
    MenuBranchCreate,
    MenuBranchPublic,
    MenuCategoryAdminPublic,
    MenuCategoryCreate,
    MenuCategoryPublic,
    MenuDishAdminPublic,
    MenuDishCard,
    MenuDishCreate,
    MenuDishImportJobResponse,
    MenuDishJobPublic,
    MenuDishJobsSummary,
    MenuFeedResponse,
    MenuMediaUploadResponse,
    MenuRestaurantPublic,
    GenerateVideosRequest,
    GenerateVideosResponse,
)
from app.services.media import (
    ALLOWED_MEDIA_EXTS,
    AUDIO_EXTS,
    IMAGE_EXTS,
    UPLOAD_DIR,
    save_upload_bytes,
)

router = APIRouter(prefix="/menu", tags=["menu"])
UPLOAD_ROOT = UPLOAD_DIR
MAX_MEDIA_SIZE_BYTES = 200 * 1024 * 1024


def _to_media_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"/api/v1/menu/media?path={path}"


def _normalize_upload_relpath(path: str | None) -> str | None:
    if not path:
        return None
    normalized = path.strip().replace("\\", "/")
    if normalized.startswith("/"):
        normalized = normalized[1:]
    return normalized or None


def _normalize_branch_name(name: str) -> str:
    return " ".join(name.strip().split())


def _normalize_category_name(name: str) -> str:
    return " ".join(name.strip().split())


def _parse_restaurant_uuid(restaurant_id: str | None) -> uuid.UUID | None:
    if not restaurant_id:
        return None
    try:
        return uuid.UUID(restaurant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный restaurant_id") from exc


def _build_category_public(category: MenuCategory, branch_name: str | None = None) -> MenuCategoryPublic:
    return MenuCategoryPublic(
        id=category.id,
        name=category.name,
        restaurant_id=str(category.restaurant_id) if category.restaurant_id else None,
        branch_id=category.branch_id,
        menu_type=branch_name or category.menu_type,
    )


def _build_category_admin_public(category: MenuCategory, branch_name: str | None = None) -> MenuCategoryAdminPublic:
    return MenuCategoryAdminPublic(
        id=category.id,
        name=category.name,
        restaurant_id=str(category.restaurant_id) if category.restaurant_id else None,
        branch_id=category.branch_id,
        menu_type=branch_name or category.menu_type,
        description=category.description,
        is_active=category.is_active,
    )


def _build_dish_admin_public(db: Session, dish: MenuDish) -> MenuDishAdminPublic:
    category = db.get(MenuCategory, dish.category_id) if dish.category_id else None
    branch_name = None
    if category and category.branch_id:
        branch = db.get(MenuBranch, category.branch_id)
        if branch:
            branch_name = branch.name
    return MenuDishAdminPublic(
        id=dish.id,
        name=dish.name,
        ingredients=dish.ingredients,
        description=dish.description,
        price=dish.price,
        price_rubles=dish.price_rubles,
        restaurant_id=str(dish.restaurant_id) if dish.restaurant_id else None,
        category_id=dish.category_id,
        category=_build_category_public(category, branch_name=branch_name) if category else None,
        is_available=dish.is_available,
        is_active=dish.is_active,
        photo_dish_path=dish.photo_dish_path,
        photo_ingredients_path=dish.photo_ingredients_path,
        audio_path=dish.audio_path,
        video_path=dish.video_path,
    )


@router.get("/restaurants", response_model=list[MenuRestaurantPublic])
def get_menu_restaurants(db: Session = Depends(get_db)):
    """Публичный список ресторанов, у которых есть активные блюда (для вкладок меню)."""
    rows = db.execute(
        select(RestaurantCatalog.id, RestaurantCatalog.name)
        .join(MenuDish, MenuDish.restaurant_id == RestaurantCatalog.id)
        .where(MenuDish.is_active.is_(True))
        .distinct()
        .order_by(RestaurantCatalog.name.asc())
    ).all()
    return [MenuRestaurantPublic(id=str(row.id), name=row.name) for row in rows]


@router.get("/categories", response_model=list[MenuCategoryPublic])
def get_menu_categories(
    restaurant_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    category_query = select(MenuCategory).where(MenuCategory.is_active.is_(True))
    restaurant_uuid = _parse_restaurant_uuid(restaurant_id)
    if restaurant_uuid:
        category_query = category_query.where(MenuCategory.restaurant_id == restaurant_uuid)
    categories = list(db.scalars(category_query.order_by(MenuCategory.name.asc())).all())
    branch_ids = {cat.branch_id for cat in categories if cat.branch_id is not None}
    branches_by_id: dict[int, MenuBranch] = {}
    if branch_ids:
        branches = list(db.scalars(select(MenuBranch).where(MenuBranch.id.in_(branch_ids))).all())
        branches_by_id = {branch.id: branch for branch in branches}
    return [
        _build_category_public(
            cat,
            branch_name=branches_by_id.get(cat.branch_id).name if cat.branch_id and branches_by_id.get(cat.branch_id) else None,
        )
        for cat in categories
    ]


@router.get("/feed", response_model=MenuFeedResponse)
def get_menu_feed(
    category: str | None = Query(default=None),
    restaurant_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    dish_query = select(MenuDish).order_by(MenuDish.id.asc())
    count_query = select(func.count(MenuDish.id))

    restaurant_uuid = _parse_restaurant_uuid(restaurant_id)
    if restaurant_uuid:
        dish_query = dish_query.where(MenuDish.restaurant_id == restaurant_uuid)
        count_query = count_query.where(MenuDish.restaurant_id == restaurant_uuid)

    if category:
        cat_query = select(MenuCategory).where(func.lower(MenuCategory.name) == category.strip().lower())
        if restaurant_uuid:
            cat_query = cat_query.where(MenuCategory.restaurant_id == restaurant_uuid)
        cat = db.scalar(cat_query)
        if not cat:
            return MenuFeedResponse(total=0, items=[])
        dish_query = dish_query.where(MenuDish.category_id == cat.id)
        count_query = count_query.where(MenuDish.category_id == cat.id)

    total = db.scalar(count_query) or 0
    dishes = list(db.scalars(dish_query.offset(offset).limit(limit)).all())

    categories_by_id: dict[int, MenuCategory] = {}
    branches_by_id: dict[int, MenuBranch] = {}
    if dishes:
        category_ids = {dish.category_id for dish in dishes if dish.category_id is not None}
        if category_ids:
            categories = list(db.scalars(select(MenuCategory).where(MenuCategory.id.in_(category_ids))).all())
            categories_by_id = {cat.id: cat for cat in categories}
            branch_ids = {cat.branch_id for cat in categories if cat.branch_id is not None}
            if branch_ids:
                branches = list(db.scalars(select(MenuBranch).where(MenuBranch.id.in_(branch_ids))).all())
                branches_by_id = {branch.id: branch for branch in branches}

    items: list[MenuDishCard] = []
    for dish in dishes:
        cat = categories_by_id.get(dish.category_id) if dish.category_id else None
        image_path = dish.photo_dish_path or dish.photo_ingredients_path
        items.append(
            MenuDishCard(
                id=dish.id,
                name=dish.name,
                ingredients=dish.ingredients,
                description=dish.description,
                price=dish.price,
                price_rubles=dish.price_rubles,
                category=_build_category_public(
                    cat,
                    branch_name=branches_by_id.get(cat.branch_id).name if cat and cat.branch_id and branches_by_id.get(cat.branch_id) else None,
                )
                if cat
                else None,
                image_url=_to_media_url(image_path),
                video_url=_to_media_url(dish.video_path),
                audio_url=_to_media_url(dish.audio_path),
            )
        )

    return MenuFeedResponse(total=total, items=items)


@router.get("/admin/branches", response_model=list[MenuBranchPublic])
def list_branches_admin(
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    branches = list(db.scalars(select(MenuBranch).order_by(MenuBranch.sort_order.asc(), MenuBranch.name.asc())).all())
    return [MenuBranchPublic(id=b.id, name=b.name, is_active=b.is_active, sort_order=b.sort_order) for b in branches]


@router.post("/admin/branches", response_model=MenuBranchPublic, status_code=status.HTTP_201_CREATED)
def create_branch_admin(
    payload: MenuBranchCreate,
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    name = _normalize_branch_name(payload.name)
    existing = db.scalar(select(MenuBranch).where(func.lower(MenuBranch.name) == name.lower()))
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ветка уже существует")
    branch = MenuBranch(name=name, is_active=payload.is_active, sort_order=payload.sort_order)
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return MenuBranchPublic(id=branch.id, name=branch.name, is_active=branch.is_active, sort_order=branch.sort_order)


@router.put("/admin/branches/{branch_id}", response_model=MenuBranchPublic)
def update_branch_admin(
    branch_id: int,
    payload: MenuBranchCreate,
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    branch = db.get(MenuBranch, branch_id)
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ветка не найдена")
    name = _normalize_branch_name(payload.name)
    duplicate = db.scalar(select(MenuBranch).where(func.lower(MenuBranch.name) == name.lower(), MenuBranch.id != branch_id))
    if duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ветка с таким именем уже существует")
    branch.name = name
    branch.is_active = payload.is_active
    branch.sort_order = payload.sort_order
    db.commit()
    db.refresh(branch)
    return MenuBranchPublic(id=branch.id, name=branch.name, is_active=branch.is_active, sort_order=branch.sort_order)


@router.delete("/admin/branches/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_branch_admin(
    branch_id: int,
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    branch = db.get(MenuBranch, branch_id)
    if not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ветка не найдена")
    categories = list(db.scalars(select(MenuCategory).where(MenuCategory.branch_id == branch_id)).all())
    for category in categories:
        category.branch_id = None
    db.delete(branch)
    db.commit()


@router.get("/admin/categories", response_model=list[MenuCategoryAdminPublic])
def list_categories_admin(
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    categories = list(db.scalars(select(MenuCategory).order_by(MenuCategory.name.asc())).all())
    branch_ids = {cat.branch_id for cat in categories if cat.branch_id is not None}
    branches_by_id: dict[int, MenuBranch] = {}
    if branch_ids:
        branches = list(db.scalars(select(MenuBranch).where(MenuBranch.id.in_(branch_ids))).all())
        branches_by_id = {branch.id: branch for branch in branches}
    return [
        _build_category_admin_public(
            cat,
            branch_name=branches_by_id.get(cat.branch_id).name if cat.branch_id and branches_by_id.get(cat.branch_id) else None,
        )
        for cat in categories
    ]


@router.post("/admin/categories", response_model=MenuCategoryAdminPublic, status_code=status.HTTP_201_CREATED)
def create_category_admin(
    payload: MenuCategoryCreate,
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    name = _normalize_category_name(payload.name)
    restaurant_uuid = _parse_restaurant_uuid(payload.restaurant_id)
    if restaurant_uuid and not db.get(RestaurantCatalog, restaurant_uuid):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ресторан не найден")
    branch = db.get(MenuBranch, payload.branch_id) if payload.branch_id else None
    if payload.branch_id and not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ветка не найдена")
    existing_query = select(MenuCategory).where(func.lower(MenuCategory.name) == name.lower())
    if restaurant_uuid:
        existing_query = existing_query.where(MenuCategory.restaurant_id == restaurant_uuid)
    else:
        existing_query = existing_query.where(MenuCategory.restaurant_id.is_(None))
    existing = db.scalar(existing_query)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Категория уже существует")
    category = MenuCategory(
        name=name,
        restaurant_id=restaurant_uuid,
        branch_id=payload.branch_id,
        menu_type=branch.name if branch else (payload.menu_type.strip() if payload.menu_type else None),
        description=payload.description.strip() if payload.description else None,
        is_active=payload.is_active,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return _build_category_admin_public(category, branch_name=branch.name if branch else None)


@router.put("/admin/categories/{category_id}", response_model=MenuCategoryAdminPublic)
def update_category_admin(
    category_id: int,
    payload: MenuCategoryCreate,
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    category = db.get(MenuCategory, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Категория не найдена")
    name = _normalize_category_name(payload.name)
    restaurant_uuid = _parse_restaurant_uuid(payload.restaurant_id)
    if restaurant_uuid and not db.get(RestaurantCatalog, restaurant_uuid):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ресторан не найден")
    branch = db.get(MenuBranch, payload.branch_id) if payload.branch_id else None
    if payload.branch_id and not branch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ветка не найдена")
    duplicate_query = select(MenuCategory).where(func.lower(MenuCategory.name) == name.lower(), MenuCategory.id != category_id)
    if restaurant_uuid:
        duplicate_query = duplicate_query.where(MenuCategory.restaurant_id == restaurant_uuid)
    else:
        duplicate_query = duplicate_query.where(MenuCategory.restaurant_id.is_(None))
    duplicate = db.scalar(duplicate_query)
    if duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Категория с таким именем уже существует")
    category.name = name
    category.restaurant_id = restaurant_uuid
    category.branch_id = payload.branch_id
    category.menu_type = branch.name if branch else (payload.menu_type.strip() if payload.menu_type else None)
    category.description = payload.description.strip() if payload.description else None
    category.is_active = payload.is_active
    db.commit()
    db.refresh(category)
    return _build_category_admin_public(category, branch_name=branch.name if branch else None)


@router.delete("/admin/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category_admin(
    category_id: int,
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    category = db.get(MenuCategory, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Категория не найдена")
    dishes = list(db.scalars(select(MenuDish).where(MenuDish.category_id == category_id)).all())
    for dish in dishes:
        dish.category_id = None
    db.delete(category)
    db.commit()


@router.get("/admin/dishes", response_model=list[MenuDishAdminPublic])
def list_dishes_admin(
    restaurant_id: str | None = Query(default=None),
    category_id: int | None = Query(default=None),
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    query = select(MenuDish).order_by(MenuDish.id.desc())
    if restaurant_id:
        try:
            query = query.where(MenuDish.restaurant_id == uuid.UUID(restaurant_id))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный restaurant_id") from exc
    if category_id is not None:
        query = query.where(MenuDish.category_id == category_id)
    dishes = list(db.scalars(query).all())
    return [_build_dish_admin_public(db, dish) for dish in dishes]


@router.post("/admin/dishes", response_model=MenuDishAdminPublic, status_code=status.HTTP_201_CREATED)
def create_dish_admin(
    payload: MenuDishCreate,
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    category = db.get(MenuCategory, payload.category_id) if payload.category_id else None
    if payload.category_id and not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Категория не найдена")

    restaurant_uuid = _parse_restaurant_uuid(payload.restaurant_id)
    if restaurant_uuid and not db.get(RestaurantCatalog, restaurant_uuid):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ресторан не найден")
    if category and category.restaurant_id and restaurant_uuid and category.restaurant_id != restaurant_uuid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Категория относится к другому ресторану",
        )
    if category and category.restaurant_id and not restaurant_uuid:
        restaurant_uuid = category.restaurant_id

    dish = MenuDish(
        name=payload.name.strip(),
        ingredients=payload.ingredients.strip() if payload.ingredients else None,
        description=payload.description.strip() if payload.description else None,
        price=payload.price,
        price_rubles=payload.price_rubles.strip() if payload.price_rubles else None,
        restaurant_id=restaurant_uuid,
        category_id=payload.category_id,
        is_available=payload.is_available,
        is_active=payload.is_active,
        photo_dish_path=_normalize_upload_relpath(payload.photo_dish_path),
        photo_ingredients_path=_normalize_upload_relpath(payload.photo_ingredients_path),
        audio_path=_normalize_upload_relpath(payload.audio_path),
        video_path=_normalize_upload_relpath(payload.video_path),
    )
    db.add(dish)
    db.commit()
    db.refresh(dish)
    return _build_dish_admin_public(db, dish)


@router.put("/admin/dishes/{dish_id}", response_model=MenuDishAdminPublic)
def update_dish_admin(
    dish_id: int,
    payload: MenuDishCreate,
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    dish = db.get(MenuDish, dish_id)
    if not dish:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Позиция не найдена")
    category = db.get(MenuCategory, payload.category_id) if payload.category_id else None
    if payload.category_id and not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Категория не найдена")

    restaurant_uuid = _parse_restaurant_uuid(payload.restaurant_id)
    if restaurant_uuid and not db.get(RestaurantCatalog, restaurant_uuid):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ресторан не найден")
    if category and category.restaurant_id and restaurant_uuid and category.restaurant_id != restaurant_uuid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Категория относится к другому ресторану",
        )
    if category and category.restaurant_id and not restaurant_uuid:
        restaurant_uuid = category.restaurant_id

    dish.name = payload.name.strip()
    dish.ingredients = payload.ingredients.strip() if payload.ingredients else None
    dish.description = payload.description.strip() if payload.description else None
    dish.price = payload.price
    dish.price_rubles = payload.price_rubles.strip() if payload.price_rubles else None
    dish.restaurant_id = restaurant_uuid
    dish.category_id = payload.category_id
    dish.is_available = payload.is_available
    dish.is_active = payload.is_active
    dish.photo_dish_path = _normalize_upload_relpath(payload.photo_dish_path)
    dish.photo_ingredients_path = _normalize_upload_relpath(payload.photo_ingredients_path)
    dish.audio_path = _normalize_upload_relpath(payload.audio_path)
    dish.video_path = _normalize_upload_relpath(payload.video_path)
    db.commit()
    db.refresh(dish)
    return _build_dish_admin_public(db, dish)


@router.delete("/admin/dishes/{dish_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dish_admin(
    dish_id: int,
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    dish = db.get(MenuDish, dish_id)
    if not dish:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Позиция не найдена")
    db.delete(dish)
    db.commit()


async def _store_upload(file: UploadFile, allowed_exts: set[str], label: str) -> str:
    """Провалидировать и сохранить загруженный файл, вернуть относительный путь."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неподдерживаемый тип файла для «{label}»",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Файл «{label}» пустой")
    if len(content) > MAX_MEDIA_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Файл «{label}» слишком большой (максимум 200 МБ)",
        )
    return save_upload_bytes(content, suffix)


@router.post("/admin/media", response_model=MenuMediaUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_media_admin(
    file: UploadFile = File(...),
    _: User = Depends(require_roles(Role.SUPERADMIN)),
):
    path = await _store_upload(file, ALLOWED_MEDIA_EXTS, "медиа")
    return MenuMediaUploadResponse(path=path)


def _build_dish_job_public(job: MenuDishVideoJob, dish: MenuDish | None = None) -> MenuDishJobPublic:
    return MenuDishJobPublic(
        id=job.id,
        dish_id=job.dish_id,
        dish_name=dish.name if dish else None,
        status=job.status,
        error=job.error,
        attempts=job.attempts,
        video_path=dish.video_path if dish else None,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post(
    "/admin/dishes/import-job",
    response_model=MenuDishImportJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_dish_job(
    name: str = Form(...),
    ingredients: str | None = Form(None),
    description: str | None = Form(None),
    price: int | None = Form(None),
    price_rubles: str | None = Form(None),
    category_id: int | None = Form(None),
    restaurant_id: str | None = Form(None),
    is_available: bool = Form(True),
    is_active: bool = Form(True),
    source_dish_key: str | None = Form(None),
    match_by_name: bool = Form(False),
    generate_video: bool = Form(True),
    photo_dish: UploadFile | None = File(None),
    photo_ingredients: UploadFile | None = File(None),
    audio: UploadFile | None = File(None),
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """Пачечная загрузка блюда (multipart) + постановка видео в очередь.

    Одно блюдо на запрос: текстовые поля + фото/аудио. Блюдо ищется по
    `source_dish_key`, а если его нет и `match_by_name=true` — по точному имени
    (в пределах ресторана); иначе создаётся новое. Текстовые поля со значением
    `None` НЕ затирают существующие (частичное обновление). Файлы обновляются
    только если переданы. При `generate_video=true` ставится задание на склейку
    видео из фото ингредиентов и озвучки — считает воркер.
    """
    if not name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пустое название блюда")

    category = db.get(MenuCategory, category_id) if category_id else None
    if category_id and not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Категория не найдена")

    restaurant_uuid = _parse_restaurant_uuid(restaurant_id)
    if restaurant_uuid and not db.get(RestaurantCatalog, restaurant_uuid):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ресторан не найден")
    if category and category.restaurant_id and restaurant_uuid and category.restaurant_id != restaurant_uuid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Категория относится к другому ресторану",
        )
    if category and category.restaurant_id and not restaurant_uuid:
        restaurant_uuid = category.restaurant_id

    # Файлы сохраняем ДО записи в БД — при ошибке валидации блюдо не создаётся.
    photo_dish_path = await _store_upload(photo_dish, IMAGE_EXTS, "фото блюда") if photo_dish else None
    photo_ingredients_path = (
        await _store_upload(photo_ingredients, IMAGE_EXTS, "фото ингредиентов") if photo_ingredients else None
    )
    audio_path = await _store_upload(audio, AUDIO_EXTS, "аудио") if audio else None

    key = source_dish_key.strip() if source_dish_key and source_dish_key.strip() else None
    dish = db.scalar(select(MenuDish).where(MenuDish.source_dish_key == key)) if key else None
    if dish is None and match_by_name:
        name_query = select(MenuDish).where(func.lower(MenuDish.name) == name.strip().lower())
        if restaurant_uuid:
            name_query = name_query.where(MenuDish.restaurant_id == restaurant_uuid)
        dish = db.scalar(name_query.order_by(MenuDish.id.asc()))

    if dish is None:
        dish = MenuDish(name=name.strip(), source_dish_key=key)
        db.add(dish)
    elif key and not dish.source_dish_key:
        dish.source_dish_key = key  # закрепить ключ за найденным по имени блюдом

    dish.name = name.strip()
    # None не затирает существующее значение (частичное обновление при повторной заливке).
    if ingredients is not None:
        dish.ingredients = ingredients.strip() or None
    if description is not None:
        dish.description = description.strip() or None
    if price is not None:
        dish.price = price if price > 0 else 0
    if price_rubles is not None:
        dish.price_rubles = price_rubles.strip() or None
    if category_id is not None:
        dish.category_id = category_id
    if restaurant_uuid:
        dish.restaurant_id = restaurant_uuid
    dish.is_available = is_available
    dish.is_active = is_active
    # Пути обновляем только если пришёл новый файл (иначе оставляем прежние).
    if photo_dish_path is not None:
        dish.photo_dish_path = photo_dish_path
    if photo_ingredients_path is not None:
        dish.photo_ingredients_path = photo_ingredients_path
    if audio_path is not None:
        dish.audio_path = audio_path

    # Проверяем достаточность медиа ДО commit — иначе при 400 осталось бы
    # наполовину созданное блюдо (сессия откатывается на выходе из get_db).
    if generate_video:
        have_photo = bool(dish.photo_ingredients_path or dish.photo_dish_path)
        have_audio = bool(dish.audio_path)
        if not have_photo or not have_audio:
            missing = []
            if not have_photo:
                missing.append("фото")
            if not have_audio:
                missing.append("аудио")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Для генерации видео не хватает: {', '.join(missing)}",
            )

    db.commit()
    db.refresh(dish)

    job: MenuDishVideoJob | None = None
    if generate_video:
        job = MenuDishVideoJob(dish_id=dish.id, status="pending")
        db.add(job)
        db.commit()
        db.refresh(job)

    return MenuDishImportJobResponse(
        dish=_build_dish_admin_public(db, dish),
        job=_build_dish_job_public(job, dish) if job else None,
    )


@router.get("/admin/dishes/import-jobs", response_model=MenuDishJobsSummary)
def list_import_jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    counts = dict(
        db.execute(
            select(MenuDishVideoJob.status, func.count(MenuDishVideoJob.id)).group_by(MenuDishVideoJob.status)
        ).all()
    )
    query = select(MenuDishVideoJob).order_by(MenuDishVideoJob.id.desc())
    if status_filter:
        query = query.where(MenuDishVideoJob.status == status_filter)
    jobs = list(db.scalars(query.limit(limit)).all())
    dish_ids = {job.dish_id for job in jobs}
    dishes_by_id: dict[int, MenuDish] = {}
    if dish_ids:
        dishes = list(db.scalars(select(MenuDish).where(MenuDish.id.in_(dish_ids))).all())
        dishes_by_id = {dish.id: dish for dish in dishes}
    return MenuDishJobsSummary(
        pending=int(counts.get("pending", 0)),
        processing=int(counts.get("processing", 0)),
        done=int(counts.get("done", 0)),
        error=int(counts.get("error", 0)),
        total=sum(int(v) for v in counts.values()),
        jobs=[_build_dish_job_public(job, dishes_by_id.get(job.dish_id)) for job in jobs],
    )


def _dish_has_media(dish: MenuDish) -> bool:
    return bool((dish.photo_ingredients_path or dish.photo_dish_path) and dish.audio_path)


def _active_video_dish_ids(db: Session, dish_ids: set[int] | None = None) -> set[int]:
    """id блюд, у которых уже есть незавершённое задание (pending/processing)."""
    query = select(MenuDishVideoJob.dish_id).where(
        MenuDishVideoJob.status.in_(("pending", "processing"))
    )
    if dish_ids is not None:
        if not dish_ids:
            return set()
        query = query.where(MenuDishVideoJob.dish_id.in_(dish_ids))
    return set(db.scalars(query).all())


@router.post("/admin/dishes/generate-videos", response_model=GenerateVideosResponse)
def generate_videos_bulk(
    payload: GenerateVideosRequest,
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """Массово поставить генерацию видео для существующих блюд.

    По умолчанию берёт блюда с фото + аудио, но БЕЗ видео, и ставит их в
    очередь (воркер склеит). `force=true` — пересоздать даже там, где видео
    уже есть. Блюда с активным заданием пропускаются (без дублей).
    """
    query = select(MenuDish).order_by(MenuDish.id.asc())
    if payload.restaurant_id:
        query = query.where(MenuDish.restaurant_id == _parse_restaurant_uuid(payload.restaurant_id))
    if payload.category_id is not None:
        query = query.where(MenuDish.category_id == payload.category_id)
    if payload.dish_ids:
        query = query.where(MenuDish.id.in_(payload.dish_ids))
    dishes = list(db.scalars(query).all())

    active_ids = _active_video_dish_ids(db, {dish.id for dish in dishes})

    enqueued = skipped_no_media = skipped_has_video = skipped_already_queued = 0
    new_jobs: list[MenuDishVideoJob] = []
    for dish in dishes:
        if not _dish_has_media(dish):
            skipped_no_media += 1
            continue
        if dish.video_path and not payload.force:
            skipped_has_video += 1
            continue
        if dish.id in active_ids:
            skipped_already_queued += 1
            continue
        new_jobs.append(MenuDishVideoJob(dish_id=dish.id, status="pending"))
        active_ids.add(dish.id)
        enqueued += 1

    if new_jobs:
        db.add_all(new_jobs)
        db.commit()

    return GenerateVideosResponse(
        total_considered=len(dishes),
        enqueued=enqueued,
        skipped_no_media=skipped_no_media,
        skipped_has_video=skipped_has_video,
        skipped_already_queued=skipped_already_queued,
    )


@router.post("/admin/dishes/{dish_id}/generate-video", response_model=MenuDishJobPublic, status_code=status.HTTP_201_CREATED)
def generate_video_single(
    dish_id: int,
    force: bool = Query(default=False),
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """Поставить (или повторить) генерацию видео для одного блюда."""
    dish = db.get(MenuDish, dish_id)
    if not dish:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Позиция не найдена")
    if not _dish_has_media(dish):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У блюда нет фото и/или аудио для генерации видео",
        )
    if not force:
        existing = db.scalar(
            select(MenuDishVideoJob)
            .where(
                MenuDishVideoJob.dish_id == dish_id,
                MenuDishVideoJob.status.in_(("pending", "processing")),
            )
            .order_by(MenuDishVideoJob.id.desc())
        )
        if existing:
            return _build_dish_job_public(existing, dish)
    job = MenuDishVideoJob(dish_id=dish_id, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)
    return _build_dish_job_public(job, dish)


import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.menu import MenuCategory, MenuDish
from app.models.user import RestaurantCatalog, Role, User
from app.schemas.menu import (
    MenuCategoryAdminPublic,
    MenuCategoryCreate,
    MenuCategoryPublic,
    MenuDishAdminPublic,
    MenuDishCard,
    MenuDishCreate,
    MenuFeedResponse,
    MenuMediaUploadResponse,
)

router = APIRouter(prefix="/menu", tags=["menu"])
UPLOAD_ROOT = Path(__file__).resolve().parents[3] / "media_uploads" / "uploads"


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


def _build_dish_admin_public(db: Session, dish: MenuDish) -> MenuDishAdminPublic:
    category = db.get(MenuCategory, dish.category_id) if dish.category_id else None
    return MenuDishAdminPublic(
        id=dish.id,
        name=dish.name,
        ingredients=dish.ingredients,
        description=dish.description,
        price=dish.price,
        price_rubles=dish.price_rubles,
        restaurant_id=str(dish.restaurant_id) if dish.restaurant_id else None,
        category_id=dish.category_id,
        category=MenuCategoryPublic(id=category.id, name=category.name, menu_type=category.menu_type) if category else None,
        is_available=dish.is_available,
        is_active=dish.is_active,
        photo_dish_path=dish.photo_dish_path,
        photo_ingredients_path=dish.photo_ingredients_path,
        audio_path=dish.audio_path,
        video_path=dish.video_path,
    )


@router.get("/categories", response_model=list[MenuCategoryPublic])
def get_menu_categories(db: Session = Depends(get_db)):
    categories = list(
        db.scalars(
            select(MenuCategory)
            .where(MenuCategory.is_active.is_(True))
            .order_by(MenuCategory.name.asc())
        ).all()
    )
    return [MenuCategoryPublic(id=cat.id, name=cat.name, menu_type=cat.menu_type) for cat in categories]


@router.get("/feed", response_model=MenuFeedResponse)
def get_menu_feed(
    category: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    dish_query = select(MenuDish).order_by(MenuDish.id.asc())
    count_query = select(func.count(MenuDish.id))

    if category:
        cat_query = select(MenuCategory).where(func.lower(MenuCategory.name) == category.strip().lower())
        cat = db.scalar(cat_query)
        if not cat:
            return MenuFeedResponse(total=0, items=[])
        dish_query = dish_query.where(MenuDish.category_id == cat.id)
        count_query = count_query.where(MenuDish.category_id == cat.id)

    total = db.scalar(count_query) or 0
    dishes = list(db.scalars(dish_query.offset(offset).limit(limit)).all())

    categories_by_id: dict[int, MenuCategory] = {}
    if dishes:
        category_ids = {dish.category_id for dish in dishes if dish.category_id is not None}
        if category_ids:
            categories = list(db.scalars(select(MenuCategory).where(MenuCategory.id.in_(category_ids))).all())
            categories_by_id = {cat.id: cat for cat in categories}

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
                category=(
                    MenuCategoryPublic(id=cat.id, name=cat.name, menu_type=cat.menu_type)
                    if cat
                    else None
                ),
                image_url=_to_media_url(image_path),
                video_url=_to_media_url(dish.video_path),
                audio_url=_to_media_url(dish.audio_path),
            )
        )

    return MenuFeedResponse(total=total, items=items)


@router.get("/admin/categories", response_model=list[MenuCategoryAdminPublic])
def list_categories_admin(
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    categories = list(db.scalars(select(MenuCategory).order_by(MenuCategory.name.asc())).all())
    return [
        MenuCategoryAdminPublic(
            id=cat.id,
            name=cat.name,
            menu_type=cat.menu_type,
            description=cat.description,
            is_active=cat.is_active,
        )
        for cat in categories
    ]


@router.post("/admin/categories", response_model=MenuCategoryAdminPublic, status_code=status.HTTP_201_CREATED)
def create_category_admin(
    payload: MenuCategoryCreate,
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    name = payload.name.strip()
    existing = db.scalar(select(MenuCategory).where(func.lower(MenuCategory.name) == name.lower()))
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Категория уже существует")
    category = MenuCategory(
        name=name,
        menu_type=payload.menu_type.strip() if payload.menu_type else None,
        description=payload.description.strip() if payload.description else None,
        is_active=payload.is_active,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return MenuCategoryAdminPublic(
        id=category.id,
        name=category.name,
        menu_type=category.menu_type,
        description=category.description,
        is_active=category.is_active,
    )


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
    name = payload.name.strip()
    duplicate = db.scalar(
        select(MenuCategory).where(func.lower(MenuCategory.name) == name.lower(), MenuCategory.id != category_id)
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Категория с таким именем уже существует")
    category.name = name
    category.menu_type = payload.menu_type.strip() if payload.menu_type else None
    category.description = payload.description.strip() if payload.description else None
    category.is_active = payload.is_active
    db.commit()
    db.refresh(category)
    return MenuCategoryAdminPublic(
        id=category.id,
        name=category.name,
        menu_type=category.menu_type,
        description=category.description,
        is_active=category.is_active,
    )


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

    restaurant_uuid = None
    if payload.restaurant_id:
        try:
            restaurant_uuid = uuid.UUID(payload.restaurant_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный restaurant_id") from exc
        restaurant = db.get(RestaurantCatalog, restaurant_uuid)
        if not restaurant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ресторан не найден")

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

    restaurant_uuid = None
    if payload.restaurant_id:
        try:
            restaurant_uuid = uuid.UUID(payload.restaurant_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный restaurant_id") from exc
        restaurant = db.get(RestaurantCatalog, restaurant_uuid)
        if not restaurant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ресторан не найден")

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


@router.post("/admin/media", response_model=MenuMediaUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_media_admin(
    file: UploadFile = File(...),
    _: User = Depends(require_roles(Role.SUPERADMIN)),
):
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "").suffix.lower()
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp3", ".wav", ".ogg", ".mp4", ".webm", ".m4a"}
    if suffix not in allowed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неподдерживаемый тип файла")
    file_name = f"{uuid.uuid4().hex}{suffix}"
    target_path = UPLOAD_ROOT / file_name
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл пустой")
    target_path.write_bytes(content)
    return MenuMediaUploadResponse(path=f"uploads/{file_name}")


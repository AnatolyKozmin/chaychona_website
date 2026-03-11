import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.checklist import (
    Checklist,
    ChecklistCompletion,
    ChecklistItem,
    ChecklistItemCompletion,
    ShiftType,
)
from app.models.user import JobTitleCatalog, RestaurantCatalog, Role, User
from app.schemas.checklist import (
    ChecklistAdminDetailPublic,
    ChecklistAdminPublic,
    ChecklistCompletionDetailPublic,
    ChecklistCompletionPublic,
    ChecklistCompletionSubmit,
    ChecklistCreate,
    ChecklistItemCompletionPublic,
    ChecklistItemPublic,
    ChecklistLearnerPublic,
    ChecklistUpdate,
    ShiftTypeCreate,
    ShiftTypePublic,
)

router = APIRouter(prefix="/checklists", tags=["checklists"])
UPLOAD_ROOT = Path(__file__).resolve().parents[3] / "media_uploads" / "checklist_photos"


def _parse_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _norm(value: str | None) -> str:
    return " ".join((value or "").strip().lower().replace("ё", "е").split())


def _media_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"/api/v1/menu/media?path={path}"


def _query_checklists_for_user(db: Session, current_user: User) -> list[Checklist]:
    checklists = list(
        db.scalars(
            select(Checklist)
            .where(Checklist.is_active.is_(True))
            .order_by(Checklist.sort_order.asc(), Checklist.id.asc())
        ).all()
    )
    if current_user.role in {Role.SUPERADMIN, Role.ADMIN}:
        return checklists

    user_restaurant = _norm(current_user.restaurant)
    user_job_title = _norm(current_user.job_title)
    filtered: list[Checklist] = []
    for cl in checklists:
        cl_restaurant = db.get(RestaurantCatalog, cl.restaurant_id) if cl.restaurant_id else None
        cl_job_title = db.get(JobTitleCatalog, cl.job_title_id) if cl.job_title_id else None
        matches_restaurant = (
            True if not cl_restaurant else (_norm(cl_restaurant.name) == user_restaurant and bool(user_restaurant))
        )
        matches_role = True if not cl_job_title else (_norm(cl_job_title.name) == user_job_title and bool(user_job_title))
        if matches_restaurant and matches_role:
            filtered.append(cl)
    return filtered


# --- Shift types (admin) ---


@router.get("/admin/shift-types", response_model=list[ShiftTypePublic])
def list_shift_types_admin(
    _: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    types = list(db.scalars(select(ShiftType).order_by(ShiftType.sort_order.asc(), ShiftType.id.asc())).all())
    return [ShiftTypePublic(id=t.id, name=t.name, is_active=t.is_active, sort_order=t.sort_order) for t in types]


@router.post("/admin/shift-types", response_model=ShiftTypePublic, status_code=status.HTTP_201_CREATED)
def create_shift_type_admin(
    payload: ShiftTypeCreate,
    _: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    st = ShiftType(name=payload.name.strip(), is_active=payload.is_active, sort_order=payload.sort_order)
    db.add(st)
    db.commit()
    db.refresh(st)
    return ShiftTypePublic(id=st.id, name=st.name, is_active=st.is_active, sort_order=st.sort_order)


@router.put("/admin/shift-types/{type_id}", response_model=ShiftTypePublic)
def update_shift_type_admin(
    type_id: int,
    payload: ShiftTypeCreate,
    _: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    st = db.get(ShiftType, type_id)
    if not st:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тип смены не найден")
    st.name = payload.name.strip()
    st.is_active = payload.is_active
    st.sort_order = payload.sort_order
    db.commit()
    db.refresh(st)
    return ShiftTypePublic(id=st.id, name=st.name, is_active=st.is_active, sort_order=st.sort_order)


@router.delete("/admin/shift-types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shift_type_admin(
    type_id: int,
    _: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    st = db.get(ShiftType, type_id)
    if not st:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тип смены не найден")
    db.delete(st)
    db.commit()


# --- Checklists (admin) ---


def _build_checklist_admin_public(db: Session, cl: Checklist) -> ChecklistAdminPublic:
    shift_type = db.get(ShiftType, cl.shift_type_id) if cl.shift_type_id else None
    restaurant = db.get(RestaurantCatalog, cl.restaurant_id) if cl.restaurant_id else None
    job_title = db.get(JobTitleCatalog, cl.job_title_id) if cl.job_title_id else None
    items_count = db.scalar(select(func.count()).select_from(ChecklistItem).where(ChecklistItem.checklist_id == cl.id)) or 0
    return ChecklistAdminPublic(
        id=cl.id,
        title=cl.title,
        shift_type_id=cl.shift_type_id,
        shift_type_name=shift_type.name if shift_type else None,
        restaurant_id=str(cl.restaurant_id) if cl.restaurant_id else None,
        restaurant_name=restaurant.name if restaurant else None,
        job_title_id=str(cl.job_title_id) if cl.job_title_id else None,
        job_title_name=job_title.name if job_title else None,
        is_active=cl.is_active,
        sort_order=cl.sort_order,
        items_count=items_count,
        created_at=cl.created_at,
    )


@router.get("/admin", response_model=list[ChecklistAdminPublic])
def list_checklists_admin(
    _: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    checklists = list(
        db.scalars(
            select(Checklist).order_by(Checklist.sort_order.asc(), Checklist.id.asc())
        ).all()
    )
    return [_build_checklist_admin_public(db, cl) for cl in checklists]


@router.post("/admin", response_model=ChecklistAdminDetailPublic, status_code=status.HTTP_201_CREATED)
def create_checklist_admin(
    payload: ChecklistCreate,
    _: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    restaurant_id = _parse_uuid(payload.restaurant_id)
    job_title_id = _parse_uuid(payload.job_title_id)
    if restaurant_id and not db.get(RestaurantCatalog, restaurant_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ресторан не найден")
    if job_title_id and not db.get(JobTitleCatalog, job_title_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Роль не найдена")
    if payload.shift_type_id and not db.get(ShiftType, payload.shift_type_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тип смены не найден")

    cl = Checklist(
        title=payload.title.strip(),
        shift_type_id=payload.shift_type_id,
        restaurant_id=restaurant_id,
        job_title_id=job_title_id,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )
    db.add(cl)
    db.flush()
    for idx, item in enumerate(payload.items):
        db.add(
            ChecklistItem(
                checklist_id=cl.id,
                title=item.title.strip(),
                requires_photo=item.requires_photo,
                sort_order=item.sort_order if item.sort_order else idx,
            )
        )
    db.commit()
    db.refresh(cl)
    return _build_checklist_admin_detail(db, cl)


def _build_checklist_admin_detail(db: Session, cl: Checklist) -> ChecklistAdminDetailPublic:
    base = _build_checklist_admin_public(db, cl)
    items = list(
        db.scalars(
            select(ChecklistItem).where(ChecklistItem.checklist_id == cl.id).order_by(ChecklistItem.sort_order.asc())
        ).all()
    )
    return ChecklistAdminDetailPublic(
        **base.model_dump(),
        items=[ChecklistItemPublic(id=i.id, title=i.title, requires_photo=i.requires_photo, sort_order=i.sort_order) for i in items],
    )


@router.get("/admin/{checklist_id}", response_model=ChecklistAdminDetailPublic)
def get_checklist_admin(
    checklist_id: int,
    _: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    cl = db.get(Checklist, checklist_id)
    if not cl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чек-лист не найден")
    return _build_checklist_admin_detail(db, cl)


@router.put("/admin/{checklist_id}", response_model=ChecklistAdminDetailPublic)
def update_checklist_admin(
    checklist_id: int,
    payload: ChecklistUpdate,
    _: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    cl = db.get(Checklist, checklist_id)
    if not cl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чек-лист не найден")

    if payload.title is not None:
        cl.title = payload.title.strip()
    if payload.shift_type_id is not None:
        if payload.shift_type_id and not db.get(ShiftType, payload.shift_type_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тип смены не найден")
        cl.shift_type_id = payload.shift_type_id
    if payload.restaurant_id is not None:
        cl.restaurant_id = _parse_uuid(payload.restaurant_id)
    if payload.job_title_id is not None:
        cl.job_title_id = _parse_uuid(payload.job_title_id)
    if payload.is_active is not None:
        cl.is_active = payload.is_active
    if payload.sort_order is not None:
        cl.sort_order = payload.sort_order

    if payload.items is not None:
        db.execute(delete(ChecklistItem).where(ChecklistItem.checklist_id == cl.id))
        for idx, item in enumerate(payload.items):
            db.add(
                ChecklistItem(
                    checklist_id=cl.id,
                    title=item.title.strip(),
                    requires_photo=item.requires_photo,
                    sort_order=item.sort_order if item.sort_order else idx,
                )
            )

    db.commit()
    db.refresh(cl)
    return _build_checklist_admin_detail(db, cl)


@router.delete("/admin/{checklist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_checklist_admin(
    checklist_id: int,
    _: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    cl = db.get(Checklist, checklist_id)
    if not cl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чек-лист не найден")
    db.delete(cl)
    db.commit()


# --- Completions (admin reports) ---


@router.get("/admin/completions", response_model=list[ChecklistCompletionPublic])
def list_completions_admin(
    checklist_id: int | None = Query(default=None),
    user_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    query = (
        select(ChecklistCompletion, Checklist, User)
        .join(Checklist, ChecklistCompletion.checklist_id == Checklist.id)
        .join(User, ChecklistCompletion.user_id == User.id)
        .order_by(ChecklistCompletion.completed_at.desc())
        .limit(limit)
    )
    if checklist_id is not None:
        query = query.where(ChecklistCompletion.checklist_id == checklist_id)
    if user_id is not None:
        try:
            user_uuid = UUID(user_id)
            query = query.where(ChecklistCompletion.user_id == user_uuid)
        except ValueError:
            pass
    rows = list(db.execute(query).all())

    result: list[ChecklistCompletionPublic] = []
    for comp, cl, user in rows:
        comp_items = db.scalar(
            select(func.count()).select_from(ChecklistItemCompletion).where(ChecklistItemCompletion.completion_id == comp.id)
        ) or 0
        result.append(
            ChecklistCompletionPublic(
                id=comp.id,
                checklist_id=comp.checklist_id,
                checklist_title=cl.title,
                user_id=str(user.id),
                user_name=user.full_name,
                completed_at=comp.completed_at,
                items_count=comp_items,
            )
        )
    return result


@router.get("/admin/completions/{completion_id}", response_model=ChecklistCompletionDetailPublic)
def get_completion_admin(
    completion_id: int,
    _: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    comp = db.get(ChecklistCompletion, completion_id)
    if not comp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Прохождение не найдено")

    cl = db.get(Checklist, comp.checklist_id)
    user = db.get(User, comp.user_id)
    shift_type = db.get(ShiftType, cl.shift_type_id) if cl and cl.shift_type_id else None

    item_completion_rows = list(
        db.execute(
            select(ChecklistItemCompletion, ChecklistItem)
            .join(ChecklistItem, ChecklistItemCompletion.checklist_item_id == ChecklistItem.id)
            .where(ChecklistItemCompletion.completion_id == comp.id)
            .order_by(ChecklistItem.sort_order.asc())
        ).all()
    )

    item_publics: list[ChecklistItemCompletionPublic] = []
    for ic, item in item_completion_rows:
        item_publics.append(
            ChecklistItemCompletionPublic(
                checklist_item_id=item.id,
                checklist_item_title=item.title,
                requires_photo=item.requires_photo,
                photo_path=ic.photo_path,
                photo_url=_media_url(ic.photo_path),
            )
        )

    return ChecklistCompletionDetailPublic(
        id=comp.id,
        checklist_id=comp.checklist_id,
        checklist_title=cl.title if cl else "",
        shift_type_name=shift_type.name if shift_type else None,
        user_id=str(user.id) if user else "",
        user_name=user.full_name if user else "",
        user_email=user.email if user else "",
        user_restaurant=user.restaurant if user else None,
        user_job_title=user.job_title if user else None,
        completed_at=comp.completed_at,
        item_completions=item_publics,
    )


# --- Checklists (learner) ---


@router.get("/my", response_model=list[ChecklistLearnerPublic])
def list_checklists_my(
    current_user: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN, Role.LEARNER)),
    db: Session = Depends(get_db),
):
    checklists = _query_checklists_for_user(db, current_user)
    result: list[ChecklistLearnerPublic] = []
    for cl in checklists:
        shift_type = db.get(ShiftType, cl.shift_type_id) if cl.shift_type_id else None
        items = list(
            db.scalars(
                select(ChecklistItem).where(ChecklistItem.checklist_id == cl.id).order_by(ChecklistItem.sort_order.asc())
            ).all()
        )
        result.append(
            ChecklistLearnerPublic(
                id=cl.id,
                title=cl.title,
                shift_type_name=shift_type.name if shift_type else None,
                items=[ChecklistItemPublic(id=i.id, title=i.title, requires_photo=i.requires_photo, sort_order=i.sort_order) for i in items],
            )
        )
    return result


@router.get("/my/{checklist_id}", response_model=ChecklistLearnerPublic)
def get_checklist_my(
    checklist_id: int,
    current_user: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN, Role.LEARNER)),
    db: Session = Depends(get_db),
):
    checklists = _query_checklists_for_user(db, current_user)
    cl = next((c for c in checklists if c.id == checklist_id), None)
    if not cl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чек-лист не найден")

    shift_type = db.get(ShiftType, cl.shift_type_id) if cl.shift_type_id else None
    items = list(
        db.scalars(
            select(ChecklistItem).where(ChecklistItem.checklist_id == cl.id).order_by(ChecklistItem.sort_order.asc())
        ).all()
    )
    return ChecklistLearnerPublic(
        id=cl.id,
        title=cl.title,
        shift_type_name=shift_type.name if shift_type else None,
        items=[ChecklistItemPublic(id=i.id, title=i.title, requires_photo=i.requires_photo, sort_order=i.sort_order) for i in items],
    )


@router.post("/my/{checklist_id}/complete")
def complete_checklist_my(
    checklist_id: int,
    payload: ChecklistCompletionSubmit,
    current_user: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN, Role.LEARNER)),
    db: Session = Depends(get_db),
):
    checklists = _query_checklists_for_user(db, current_user)
    cl = next((c for c in checklists if c.id == checklist_id), None)
    if not cl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чек-лист не найден")

    items = list(
        db.scalars(
            select(ChecklistItem).where(ChecklistItem.checklist_id == cl.id).order_by(ChecklistItem.sort_order.asc())
        ).all()
    )
    item_ids = {i.id for i in items}
    completion_by_item = {ic.checklist_item_id: ic for ic in payload.item_completions}

    completion = ChecklistCompletion(checklist_id=cl.id, user_id=current_user.id)
    db.add(completion)
    db.flush()

    for item in items:
        ic = completion_by_item.get(item.id)
        photo_path = ic.photo_path if ic else None
        if item.requires_photo and not photo_path:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Для пункта «{item.title}» требуется фото",
            )
        db.add(
            ChecklistItemCompletion(
                completion_id=completion.id,
                checklist_item_id=item.id,
                photo_path=photo_path,
            )
        )

    db.commit()
    return {"id": completion.id, "completed_at": completion.completed_at.isoformat()}


# --- Media upload (for checklist photos, any authenticated user) ---


@router.post("/media")
async def upload_checklist_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN, Role.LEARNER)),
):
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    suffix = (Path(file.filename or "").suffix or ".jpg").lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Разрешены только изображения: jpg, png, webp")
    file_name = f"{uuid.uuid4().hex}{suffix}"
    target_path = UPLOAD_ROOT / file_name
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл пустой")
    target_path.write_bytes(content)
    return {"path": f"checklist_photos/{file_name}"}

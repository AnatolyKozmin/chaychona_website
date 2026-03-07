from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.course import Course, CourseBlock, CourseSubBlock
from app.models.quiz import QuizTest
from app.models.user import JobTitleCatalog, RestaurantCatalog, Role, User
from app.schemas.course import (
    CourseBlockPublic,
    CourseCreate,
    CourseLinkedTestPublic,
    CoursePublic,
    CourseSubBlockPublic,
)

router = APIRouter(prefix="/courses", tags=["courses"])


def _media_url(path: str | None) -> str | None:
    if not path:
        return None
    return f"/api/v1/menu/media?path={path}"


def _norm(value: str | None) -> str:
    return " ".join((value or "").strip().lower().replace("ё", "е").split())


def _parse_uuid_or_400(value: str | None, field_name: str) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Некорректный {field_name}") from exc


def _build_course_public(db: Session, course: Course) -> CoursePublic:
    restaurant = db.get(RestaurantCatalog, course.restaurant_id) if course.restaurant_id else None
    job_title = db.get(JobTitleCatalog, course.job_title_id) if course.job_title_id else None
    linked_test = db.get(QuizTest, course.linked_test_id) if course.linked_test_id else None
    blocks = list(
        db.scalars(select(CourseBlock).where(CourseBlock.course_id == course.id).order_by(CourseBlock.sort_order.asc())).all()
    )
    blocks_public: list[CourseBlockPublic] = []
    for block in blocks:
        subblocks = list(
            db.scalars(
                select(CourseSubBlock).where(CourseSubBlock.block_id == block.id).order_by(CourseSubBlock.sort_order.asc())
            ).all()
        )
        blocks_public.append(
            CourseBlockPublic(
                id=block.id,
                heading=block.heading,
                text=block.text,
                image_path=block.image_path,
                image_url=_media_url(block.image_path),
                sort_order=block.sort_order,
                subblocks=[
                    CourseSubBlockPublic(
                        id=sub.id,
                        heading=sub.heading,
                        text=sub.text,
                        image_path=sub.image_path,
                        image_url=_media_url(sub.image_path),
                        sort_order=sub.sort_order,
                    )
                    for sub in subblocks
                ],
            )
        )

    return CoursePublic(
        id=course.id,
        title=course.title,
        description=course.description,
        restaurant_id=str(course.restaurant_id) if course.restaurant_id else None,
        restaurant_name=restaurant.name if restaurant else None,
        job_title_id=str(course.job_title_id) if course.job_title_id else None,
        job_title_name=job_title.name if job_title else None,
        linked_test=CourseLinkedTestPublic(id=linked_test.id, title=linked_test.title) if linked_test else None,
        is_active=course.is_active,
        created_at=course.created_at,
        blocks=blocks_public,
    )


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_required_text(value: str | None, field_name: str) -> str:
    normalized = _normalize_optional_text(value)
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Поле {field_name} не может быть пустым")
    return normalized


def _replace_blocks(db: Session, course_id: int, blocks_data):
    if not blocks_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Добавьте хотя бы один блок")
    existing = list(db.scalars(select(CourseBlock).where(CourseBlock.course_id == course_id)).all())
    for block in existing:
        subblocks = list(db.scalars(select(CourseSubBlock).where(CourseSubBlock.block_id == block.id)).all())
        for subblock in subblocks:
            db.delete(subblock)
        db.delete(block)
    db.flush()
    for idx, block in enumerate(blocks_data):
        subblocks_data = getattr(block, "subblocks", None) or []
        db_block = CourseBlock(
            course_id=course_id,
            heading=_normalize_optional_text(getattr(block, "heading", None)),
            text=_normalize_required_text(getattr(block, "text", None), "text"),
            image_path=_normalize_optional_text(getattr(block, "image_path", None)),
            sort_order=block.sort_order if block.sort_order is not None else idx,
        )
        db.add(db_block)
        db.flush([db_block])
        for sub_idx, sub in enumerate(subblocks_data):
            db.add(
                CourseSubBlock(
                    block_id=db_block.id,
                    heading=_normalize_optional_text(getattr(sub, "heading", None)),
                    text=_normalize_required_text(getattr(sub, "text", None), "subblock.text"),
                    image_path=_normalize_optional_text(getattr(sub, "image_path", None)),
                    sort_order=sub.sort_order if sub.sort_order is not None else sub_idx,
                )
            )


@router.get("/admin", response_model=list[CoursePublic])
def list_courses_admin(
    _: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    courses = list(db.scalars(select(Course).order_by(Course.created_at.desc())).all())
    return [_build_course_public(db, course) for course in courses]


@router.post("/admin", response_model=CoursePublic, status_code=status.HTTP_201_CREATED)
def create_course_admin(
    payload: CourseCreate,
    _: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    restaurant_id = _parse_uuid_or_400(payload.restaurant_id, "restaurant_id")
    job_title_id = _parse_uuid_or_400(payload.job_title_id, "job_title_id")
    if restaurant_id and not db.get(RestaurantCatalog, restaurant_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ресторан не найден")
    if job_title_id:
        role = db.get(JobTitleCatalog, job_title_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Роль не найдена")
        if restaurant_id and role.restaurant_id != restaurant_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Роль не принадлежит ресторану")
    if payload.linked_test_id and not db.get(QuizTest, payload.linked_test_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тест не найден")

    course = Course(
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        restaurant_id=restaurant_id,
        job_title_id=job_title_id,
        linked_test_id=payload.linked_test_id,
        is_active=payload.is_active,
    )
    db.add(course)
    try:
        db.flush([course])
        _replace_blocks(db, course.id, payload.blocks)
        db.commit()
    except (SQLAlchemyError, HTTPException):
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Ошибка сохранения курса: {exc}") from exc
    return _build_course_public(db, course)


@router.put("/admin/{course_id}", response_model=CoursePublic)
def update_course_admin(
    course_id: int,
    payload: CourseCreate,
    _: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Курс не найден")
    restaurant_id = _parse_uuid_or_400(payload.restaurant_id, "restaurant_id")
    job_title_id = _parse_uuid_or_400(payload.job_title_id, "job_title_id")
    if restaurant_id and not db.get(RestaurantCatalog, restaurant_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ресторан не найден")
    if job_title_id:
        role = db.get(JobTitleCatalog, job_title_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Роль не найдена")
        if restaurant_id and role.restaurant_id != restaurant_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Роль не принадлежит ресторану")
    if payload.linked_test_id and not db.get(QuizTest, payload.linked_test_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тест не найден")

    course.title = payload.title.strip()
    course.description = payload.description.strip() if payload.description else None
    course.restaurant_id = restaurant_id
    course.job_title_id = job_title_id
    course.linked_test_id = payload.linked_test_id
    course.is_active = payload.is_active
    try:
        _replace_blocks(db, course.id, payload.blocks)
        db.commit()
    except (SQLAlchemyError, HTTPException):
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Ошибка обновления курса: {exc}") from exc
    return _build_course_public(db, course)


@router.delete("/admin/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course_admin(
    course_id: int,
    _: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Курс не найден")
    blocks = list(db.scalars(select(CourseBlock).where(CourseBlock.course_id == course.id)).all())
    for block in blocks:
        subblocks = list(db.scalars(select(CourseSubBlock).where(CourseSubBlock.block_id == block.id)).all())
        for subblock in subblocks:
            db.delete(subblock)
        db.delete(block)
    db.delete(course)
    db.commit()


@router.get("/my", response_model=list[CoursePublic])
def list_my_courses(
    current_user: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN, Role.LEARNER)),
    db: Session = Depends(get_db),
):
    courses = list(db.scalars(select(Course).where(Course.is_active.is_(True)).order_by(Course.created_at.desc())).all())
    if current_user.role in {Role.SUPERADMIN, Role.ADMIN}:
        return [_build_course_public(db, course) for course in courses]

    user_restaurant = _norm(current_user.restaurant)
    user_job_title = _norm(current_user.job_title)
    filtered: list[Course] = []
    for course in courses:
        course_restaurant = db.get(RestaurantCatalog, course.restaurant_id) if course.restaurant_id else None
        course_job_title = db.get(JobTitleCatalog, course.job_title_id) if course.job_title_id else None
        matches_restaurant = (
            True if not course_restaurant else (_norm(course_restaurant.name) == user_restaurant and bool(user_restaurant))
        )
        matches_role = True if not course_job_title else (_norm(course_job_title.name) == user_job_title and bool(user_job_title))
        if matches_restaurant and matches_role:
            filtered.append(course)
    return [_build_course_public(db, course) for course in filtered]

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.course import Course, CourseAssignment, CourseBlock, CourseBlockProgress, CourseSubBlock
from app.models.quiz import QuizAttempt, QuizTest
from app.models.user import JobTitleCatalog, RestaurantCatalog, Role, User
from app.schemas.course import (
    CourseAssignmentPublic,
    CourseBlockPublic,
    CourseCreate,
    CourseLearnerBlockProgressPublic,
    CourseLearnerLinkedTestStatsPublic,
    CourseLearnerOverviewPublic,
    CourseLearnerStudyPublic,
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


def _validate_restaurant_role(
    db: Session, restaurant_id: UUID, job_title_id: UUID
) -> tuple[RestaurantCatalog, JobTitleCatalog]:
    restaurant = db.get(RestaurantCatalog, restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ресторан не найден")
    job_title = db.get(JobTitleCatalog, job_title_id)
    if not job_title:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Роль не найдена")
    if job_title.restaurant_id != restaurant.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Выбранная роль не принадлежит выбранному ресторану",
        )
    return restaurant, job_title


def _resolve_course_assignments(
    db: Session, payload: CourseCreate
) -> list[tuple[RestaurantCatalog, JobTitleCatalog]]:
    """Собрать пары (ресторан, роль) из payload.assignments или из одиночных полей (legacy).

    В отличие от тестов пустой список допустим — стандарт доступен всем.
    Возвращает провалидированный список без дубликатов, сохраняя порядок.
    """
    raw_pairs: list[tuple[str, str]] = []
    if payload.assignments:
        raw_pairs = [(a.restaurant_id, a.job_title_id) for a in payload.assignments]
    elif payload.restaurant_id and payload.job_title_id:
        raw_pairs = [(payload.restaurant_id, payload.job_title_id)]

    resolved: list[tuple[RestaurantCatalog, JobTitleCatalog]] = []
    seen: set[tuple[UUID, UUID]] = set()
    for restaurant_id_raw, job_title_id_raw in raw_pairs:
        restaurant_id = _parse_uuid_or_400(restaurant_id_raw, "id ресторана")
        job_title_id = _parse_uuid_or_400(job_title_id_raw, "id роли")
        if restaurant_id is None or job_title_id is None:
            continue
        key = (restaurant_id, job_title_id)
        if key in seen:
            continue
        seen.add(key)
        resolved.append(_validate_restaurant_role(db, restaurant_id, job_title_id))
    return resolved


def _sync_course_assignments(
    db: Session, course: Course, pairs: list[tuple[RestaurantCatalog, JobTitleCatalog]]
) -> None:
    """Привести строки course_assignments в соответствие со списком pairs."""
    wanted = {(restaurant.id, job_title.id) for restaurant, job_title in pairs}
    existing = list(db.scalars(select(CourseAssignment).where(CourseAssignment.course_id == course.id)).all())
    existing_keys = {(a.restaurant_id, a.job_title_id) for a in existing}

    for assignment in existing:
        if (assignment.restaurant_id, assignment.job_title_id) not in wanted:
            db.delete(assignment)
    for restaurant, job_title in pairs:
        if (restaurant.id, job_title.id) not in existing_keys:
            db.add(CourseAssignment(course_id=course.id, restaurant_id=restaurant.id, job_title_id=job_title.id))


def _build_course_assignments(db: Session, course: Course) -> list[CourseAssignmentPublic]:
    rows = list(
        db.scalars(select(CourseAssignment).where(CourseAssignment.course_id == course.id)).all()
    )
    result: list[CourseAssignmentPublic] = []
    for row in rows:
        restaurant = db.get(RestaurantCatalog, row.restaurant_id)
        job_title = db.get(JobTitleCatalog, row.job_title_id)
        if not restaurant or not job_title:
            continue
        result.append(
            CourseAssignmentPublic(
                restaurant_id=str(restaurant.id),
                restaurant_name=restaurant.name,
                job_title_id=str(job_title.id),
                job_title_name=job_title.name,
            )
        )
    result.sort(key=lambda a: (a.restaurant_name.lower(), a.job_title_name.lower()))
    return result


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
        assignments=_build_course_assignments(db, course),
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


def _query_courses_for_user(db: Session, current_user: User) -> list[Course]:
    courses = list(db.scalars(select(Course).where(Course.is_active.is_(True)).order_by(Course.created_at.desc())).all())
    if current_user.role in {Role.SUPERADMIN, Role.ADMIN}:
        return courses

    user_restaurant = _norm(current_user.restaurant)
    user_job_title = _norm(current_user.job_title)
    filtered: list[Course] = []
    for course in courses:
        assignments = list(
            db.scalars(select(CourseAssignment).where(CourseAssignment.course_id == course.id)).all()
        )
        if assignments:
            # Есть явные назначения — доступ, если совпадает хотя бы одна пара (ресторан + роль).
            matched = False
            for assignment in assignments:
                a_restaurant = db.get(RestaurantCatalog, assignment.restaurant_id)
                a_job_title = db.get(JobTitleCatalog, assignment.job_title_id)
                if not a_restaurant or not a_job_title:
                    continue
                if (
                    bool(user_restaurant)
                    and bool(user_job_title)
                    and _norm(a_restaurant.name) == user_restaurant
                    and _norm(a_job_title.name) == user_job_title
                ):
                    matched = True
                    break
            if matched:
                filtered.append(course)
            continue

        # Нет назначений — legacy: NULL в паре означает «доступно всем».
        course_restaurant = db.get(RestaurantCatalog, course.restaurant_id) if course.restaurant_id else None
        course_job_title = db.get(JobTitleCatalog, course.job_title_id) if course.job_title_id else None
        matches_restaurant = (
            True if not course_restaurant else (_norm(course_restaurant.name) == user_restaurant and bool(user_restaurant))
        )
        matches_role = True if not course_job_title else (_norm(course_job_title.name) == user_job_title and bool(user_job_title))
        if matches_restaurant and matches_role:
            filtered.append(course)
    return filtered


def _build_linked_test_stats(db: Session, current_user: User, course: Course) -> CourseLearnerLinkedTestStatsPublic | None:
    if not course.linked_test_id:
        return None
    linked_test = db.get(QuizTest, course.linked_test_id)
    if not linked_test:
        return None
    attempts = list(
        db.scalars(
            select(QuizAttempt)
            .where(QuizAttempt.user_id == current_user.id, QuizAttempt.test_id == course.linked_test_id)
            .order_by(QuizAttempt.finished_at.desc())
        ).all()
    )
    if not attempts:
        return CourseLearnerLinkedTestStatsPublic(
            test_id=linked_test.id,
            test_title=linked_test.title,
            attempts_count=0,
            best_score_percent=None,
            last_score_percent=None,
            last_attempt_at=None,
        )

    def score_percent(attempt: QuizAttempt) -> float:
        if attempt.total_questions <= 0:
            return 0.0
        return (attempt.correct_answers / attempt.total_questions) * 100.0

    best = max(score_percent(a) for a in attempts)
    last = score_percent(attempts[0])
    return CourseLearnerLinkedTestStatsPublic(
        test_id=linked_test.id,
        test_title=linked_test.title,
        attempts_count=len(attempts),
        best_score_percent=round(best, 2),
        last_score_percent=round(last, 2),
        last_attempt_at=attempts[0].finished_at,
    )


def _build_blocks_progress(
    db: Session, current_user: User, course: Course
) -> tuple[list[CourseLearnerBlockProgressPublic], int, int, float]:
    blocks = list(
        db.scalars(select(CourseBlock).where(CourseBlock.course_id == course.id).order_by(CourseBlock.sort_order.asc())).all()
    )
    progress_rows = list(
        db.scalars(
            select(CourseBlockProgress).where(
                CourseBlockProgress.user_id == current_user.id, CourseBlockProgress.course_id == course.id
            )
        ).all()
    )
    completed_by_block_id = {row.block_id: row for row in progress_rows}
    blocks_progress: list[CourseLearnerBlockProgressPublic] = []
    completed_so_far = 0
    for idx, block in enumerate(blocks):
        row = completed_by_block_id.get(block.id)
        is_completed = row is not None
        is_unlocked = idx == 0 or completed_so_far == idx
        blocks_progress.append(
            CourseLearnerBlockProgressPublic(
                block_id=block.id,
                title=block.heading or f"Блок {idx + 1}",
                sort_order=block.sort_order,
                is_completed=is_completed,
                completed_at=row.completed_at if row else None,
                is_unlocked=is_unlocked or is_completed,
            )
        )
        if is_completed:
            completed_so_far += 1

    total = len(blocks)
    completed = sum(1 for block in blocks if block.id in completed_by_block_id)
    percent = round((completed / total) * 100.0, 2) if total > 0 else 0.0
    return blocks_progress, completed, total, percent


def _replace_blocks(db: Session, course_id: int, blocks_data):
    if not blocks_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Добавьте хотя бы один блок")
    block_ids = list(db.scalars(select(CourseBlock.id).where(CourseBlock.course_id == course_id)).all())
    if block_ids:
        # Блоки пересоздаются с новыми id — старый прогресс не сопоставить,
        # без чистки FK не даст удалить блоки.
        db.execute(delete(CourseBlockProgress).where(CourseBlockProgress.course_id == course_id))
        db.execute(delete(CourseSubBlock).where(CourseSubBlock.block_id.in_(block_ids)))
    db.execute(delete(CourseBlock).where(CourseBlock.course_id == course_id))
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
    pairs = _resolve_course_assignments(db, payload)
    primary_restaurant = pairs[0][0] if pairs else None
    primary_job_title = pairs[0][1] if pairs else None
    if payload.linked_test_id and not db.get(QuizTest, payload.linked_test_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тест не найден")

    course = Course(
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        restaurant_id=primary_restaurant.id if primary_restaurant else None,
        job_title_id=primary_job_title.id if primary_job_title else None,
        linked_test_id=payload.linked_test_id,
        is_active=payload.is_active,
    )
    db.add(course)
    try:
        db.flush([course])
        _sync_course_assignments(db, course, pairs)
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
    pairs = _resolve_course_assignments(db, payload)
    primary_restaurant = pairs[0][0] if pairs else None
    primary_job_title = pairs[0][1] if pairs else None
    if payload.linked_test_id and not db.get(QuizTest, payload.linked_test_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тест не найден")

    course.title = payload.title.strip()
    course.description = payload.description.strip() if payload.description else None
    course.restaurant_id = primary_restaurant.id if primary_restaurant else None
    course.job_title_id = primary_job_title.id if primary_job_title else None
    course.linked_test_id = payload.linked_test_id
    course.is_active = payload.is_active
    try:
        _sync_course_assignments(db, course, pairs)
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
    db.execute(delete(CourseAssignment).where(CourseAssignment.course_id == course.id))
    db.execute(delete(CourseBlockProgress).where(CourseBlockProgress.course_id == course.id))
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
    courses = _query_courses_for_user(db, current_user)
    return [_build_course_public(db, course) for course in courses]


@router.get("/my-overview", response_model=list[CourseLearnerOverviewPublic])
def list_my_courses_overview(
    current_user: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN, Role.LEARNER)),
    db: Session = Depends(get_db),
):
    courses = _query_courses_for_user(db, current_user)
    response: list[CourseLearnerOverviewPublic] = []
    for course in courses:
        course_public = _build_course_public(db, course)
        blocks_progress, completed_blocks, total_blocks, progress_percent = _build_blocks_progress(db, current_user, course)
        response.append(
            CourseLearnerOverviewPublic(
                id=course_public.id,
                title=course_public.title,
                description=course_public.description,
                restaurant_name=course_public.restaurant_name,
                job_title_name=course_public.job_title_name,
                total_blocks=total_blocks,
                completed_blocks=completed_blocks,
                progress_percent=progress_percent,
                is_completed=bool(total_blocks > 0 and completed_blocks >= total_blocks),
                blocks=blocks_progress,
                linked_test_stats=_build_linked_test_stats(db, current_user, course),
            )
        )
    return response


@router.get("/my/{course_id}/study", response_model=CourseLearnerStudyPublic)
def get_my_course_study(
    course_id: int,
    current_user: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN, Role.LEARNER)),
    db: Session = Depends(get_db),
):
    courses = _query_courses_for_user(db, current_user)
    course = next((item for item in courses if item.id == course_id), None)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Курс не найден")
    course_public = _build_course_public(db, course)
    blocks_progress, _, _, progress_percent = _build_blocks_progress(db, current_user, course)
    return CourseLearnerStudyPublic(
        course=course_public,
        blocks_progress=blocks_progress,
        progress_percent=progress_percent,
        linked_test_stats=_build_linked_test_stats(db, current_user, course),
    )


@router.post("/my/{course_id}/blocks/{block_id}/complete", response_model=CourseLearnerStudyPublic)
def complete_my_course_block(
    course_id: int,
    block_id: int,
    current_user: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN, Role.LEARNER)),
    db: Session = Depends(get_db),
):
    courses = _query_courses_for_user(db, current_user)
    course = next((item for item in courses if item.id == course_id), None)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Курс не найден")

    blocks = list(
        db.scalars(select(CourseBlock).where(CourseBlock.course_id == course.id).order_by(CourseBlock.sort_order.asc())).all()
    )
    if not blocks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="У курса нет блоков")
    block_ids = [item.id for item in blocks]
    if block_id not in block_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Блок не найден")
    block_index = block_ids.index(block_id)

    if block_index > 0:
        prev_block_id = block_ids[block_index - 1]
        prev_progress = db.scalar(
            select(CourseBlockProgress).where(
                CourseBlockProgress.user_id == current_user.id,
                CourseBlockProgress.course_id == course.id,
                CourseBlockProgress.block_id == prev_block_id,
            )
        )
        if not prev_progress:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сначала завершите предыдущий блок")

    progress = db.scalar(
        select(CourseBlockProgress).where(
            CourseBlockProgress.user_id == current_user.id,
            CourseBlockProgress.course_id == course.id,
            CourseBlockProgress.block_id == block_id,
        )
    )
    if not progress:
        db.add(CourseBlockProgress(user_id=current_user.id, course_id=course.id, block_id=block_id))
        db.commit()

    course_public = _build_course_public(db, course)
    blocks_progress, _, _, progress_percent = _build_blocks_progress(db, current_user, course)
    return CourseLearnerStudyPublic(
        course=course_public,
        blocks_progress=blocks_progress,
        progress_percent=progress_percent,
        linked_test_stats=_build_linked_test_stats(db, current_user, course),
    )

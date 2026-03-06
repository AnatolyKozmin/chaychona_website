from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.menu import MenuCategory, MenuDish
from app.models.quiz import QuizAttempt, QuizTest
from app.models.user import RestaurantCatalog, Role, User
from app.schemas.dashboard import (
    DashboardOverviewResponse,
    DashboardProductStat,
    DashboardRestaurantStat,
    DashboardTopResultItem,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


@router.get("/overview", response_model=DashboardOverviewResponse)
def dashboard_overview(
    _: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    day_start = now - timedelta(days=1)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    tests_created_total = db.scalar(select(func.count(QuizTest.id))) or 0
    products_total = db.scalar(select(func.count(MenuDish.id))) or 0

    attempts_day = db.scalar(select(func.count(QuizAttempt.id)).where(QuizAttempt.finished_at >= day_start)) or 0
    attempts_week = db.scalar(select(func.count(QuizAttempt.id)).where(QuizAttempt.finished_at >= week_start)) or 0
    attempts_month = db.scalar(select(func.count(QuizAttempt.id)).where(QuizAttempt.finished_at >= month_start)) or 0

    dishes_by_category_rows = (
        db.execute(
            select(MenuCategory.menu_type, func.count(MenuDish.id))
            .select_from(MenuDish)
            .join(MenuCategory, MenuCategory.id == MenuDish.category_id, isouter=True)
            .group_by(MenuCategory.menu_type)
            .order_by(func.count(MenuDish.id).desc())
        )
        .all()
    )
    products_by_bucket = [
        DashboardProductStat(bucket=(bucket or "Без типа"), items_count=count)
        for bucket, count in dishes_by_category_rows
    ]

    restaurants = list(db.scalars(select(RestaurantCatalog).order_by(RestaurantCatalog.name.asc())).all())
    test_count_rows = db.execute(
        select(QuizTest.restaurant_id, func.count(QuizTest.id)).group_by(QuizTest.restaurant_id)
    ).all()
    tests_by_restaurant = {str(restaurant_id): count for restaurant_id, count in test_count_rows}

    learner_rows = db.execute(
        select(User.restaurant, func.count(User.id))
        .where(User.role == Role.LEARNER, User.restaurant.is_not(None))
        .group_by(User.restaurant)
    ).all()
    learners_by_restaurant_name = {_norm(name): count for name, count in learner_rows}

    restaurant_stats = [
        DashboardRestaurantStat(
            restaurant_id=str(restaurant.id),
            restaurant_name=restaurant.name,
            tests_count=tests_by_restaurant.get(str(restaurant.id), 0),
            learners_count=learners_by_restaurant_name.get(_norm(restaurant.name), 0),
        )
        for restaurant in restaurants
    ]

    attempts = list(db.scalars(select(QuizAttempt).order_by(QuizAttempt.finished_at.desc())).all())
    users_by_id: dict = {}
    if attempts:
        user_ids = {attempt.user_id for attempt in attempts}
        users = list(db.scalars(select(User).where(User.id.in_(user_ids))).all())
        users_by_id = {user.id: user for user in users}

    top_bucket: dict = {}
    for attempt in attempts:
        if attempt.total_questions <= 0:
            continue
        user = users_by_id.get(attempt.user_id)
        if not user:
            continue
        score = (attempt.correct_answers / attempt.total_questions) * 100
        bucket = top_bucket.setdefault(
            attempt.user_id,
            {
                "user": user,
                "attempts_count": 0,
                "sum_score": 0.0,
                "best_score": 0.0,
                "last_attempt_at": None,
            },
        )
        bucket["attempts_count"] += 1
        bucket["sum_score"] += score
        bucket["best_score"] = max(bucket["best_score"], score)
        if bucket["last_attempt_at"] is None or attempt.finished_at > bucket["last_attempt_at"]:
            bucket["last_attempt_at"] = attempt.finished_at

    top_results: list[DashboardTopResultItem] = []
    for user_id, bucket in top_bucket.items():
        attempts_count = bucket["attempts_count"]
        avg_score = bucket["sum_score"] / attempts_count if attempts_count else 0.0
        user = bucket["user"]
        top_results.append(
            DashboardTopResultItem(
                user_id=str(user_id),
                user_name=user.full_name,
                user_email=user.email,
                attempts_count=attempts_count,
                avg_score_percent=avg_score,
                best_score_percent=bucket["best_score"],
                last_attempt_at=bucket["last_attempt_at"],
            )
        )
    top_results.sort(key=lambda item: (-item.avg_score_percent, -item.attempts_count, -item.best_score_percent))

    return DashboardOverviewResponse(
        tests_created_total=tests_created_total,
        products_total=products_total,
        attempts_day=attempts_day,
        attempts_week=attempts_week,
        attempts_month=attempts_month,
        products_by_bucket=products_by_bucket,
        restaurants=restaurant_stats,
        top_results=top_results[:10],
    )

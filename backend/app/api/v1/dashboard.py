from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.course import Course
from app.models.menu import MenuCategory, MenuDish
from app.models.quiz import QuizAttempt, QuizTest
from app.models.user import JobTitleCatalog, RestaurantCatalog, Role, User
from app.schemas.dashboard import (
    DashboardLearnerDailyPoint,
    DashboardLearnerOverviewResponse,
    DashboardLearnerResultItem,
    DashboardOverviewResponse,
    DashboardProductStat,
    DashboardRestaurantStat,
    DashboardTopResultItem,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _query_tests_for_user(db: Session, user: User) -> list[QuizTest]:
    tests = list(db.scalars(select(QuizTest).order_by(QuizTest.created_at.desc())).all())
    if user.role != Role.LEARNER:
        return tests
    user_restaurant = _norm(user.restaurant)
    user_job_title = _norm(user.job_title)
    if not user_restaurant or not user_job_title:
        return []
    matched: list[QuizTest] = []
    for test in tests:
        restaurant = db.get(RestaurantCatalog, test.restaurant_id)
        job_title = db.get(JobTitleCatalog, test.job_title_id)
        if not restaurant or not job_title:
            continue
        if _norm(restaurant.name) == user_restaurant and _norm(job_title.name) == user_job_title:
            matched.append(test)
    return matched


def _query_courses_for_user(db: Session, user: User) -> list[Course]:
    courses = list(db.scalars(select(Course).where(Course.is_active.is_(True)).order_by(Course.created_at.desc())).all())
    if user.role != Role.LEARNER:
        return courses
    user_restaurant = _norm(user.restaurant)
    user_job_title = _norm(user.job_title)
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
    return filtered


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


@router.get("/me-overview", response_model=DashboardLearnerOverviewResponse)
def dashboard_me_overview(
    current_user: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN, Role.LEARNER)),
    db: Session = Depends(get_db),
):
    courses = _query_courses_for_user(db, current_user)
    tests = _query_tests_for_user(db, current_user)
    attempts = list(
        db.scalars(
            select(QuizAttempt).where(QuizAttempt.user_id == current_user.id).order_by(QuizAttempt.finished_at.desc())
        ).all()
    )
    attempted_test_ids = {attempt.test_id for attempt in attempts}
    completed_trainings = 0
    for course in courses:
        if course.linked_test_id is None or course.linked_test_id in attempted_test_ids:
            completed_trainings += 1
    total_trainings = len(courses)
    completed_percent = (completed_trainings / total_trainings * 100) if total_trainings else 0.0

    test_stats: dict[int, dict] = {}
    for attempt in attempts:
        if attempt.total_questions <= 0:
            continue
        score = (attempt.correct_answers / attempt.total_questions) * 100
        bucket = test_stats.setdefault(
            attempt.test_id,
            {"sum_score": 0.0, "count": 0, "last_finished_at": attempt.finished_at},
        )
        bucket["sum_score"] += score
        bucket["count"] += 1
        if attempt.finished_at > bucket["last_finished_at"]:
            bucket["last_finished_at"] = attempt.finished_at

    best_result = None
    worst_result = None
    for test_id, stats in test_stats.items():
        avg_score = stats["sum_score"] / stats["count"] if stats["count"] else 0.0
        candidate = (test_id, avg_score, stats["last_finished_at"])
        if best_result is None or avg_score > best_result[1]:
            best_result = candidate
        if worst_result is None or avg_score < worst_result[1]:
            worst_result = candidate

    def build_result_item(result_tuple):
        if result_tuple is None:
            return None
        test_id, score, finished_at = result_tuple
        test = db.get(QuizTest, test_id)
        return DashboardLearnerResultItem(
            test_id=test_id,
            test_title=test.title if test else "",
            score_percent=score,
            finished_at=finished_at,
        )

    today = datetime.utcnow().date()
    daily_points: list[DashboardLearnerDailyPoint] = []
    attempts_last_7_days = 0
    scores_last_7_days: list[float] = []
    attempts_by_day: dict = {}
    for attempt in attempts:
        if attempt.total_questions <= 0:
            continue
        day = attempt.finished_at.date()
        score = (attempt.correct_answers / attempt.total_questions) * 100
        bucket = attempts_by_day.setdefault(day, {"attempts": 0, "scores": []})
        bucket["attempts"] += 1
        bucket["scores"].append(score)
        if day >= today - timedelta(days=6):
            attempts_last_7_days += 1
            scores_last_7_days.append(score)

    for shift in range(6, -1, -1):
        day = today - timedelta(days=shift)
        bucket = attempts_by_day.get(day, {"attempts": 0, "scores": []})
        avg_score_for_day = (sum(bucket["scores"]) / len(bucket["scores"])) if bucket["scores"] else 0.0
        daily_points.append(
            DashboardLearnerDailyPoint(
                date=day.isoformat(),
                attempts=bucket["attempts"],
                avg_score_percent=avg_score_for_day,
            )
        )

    attempt_days = sorted({attempt.finished_at.date() for attempt in attempts})
    current_streak = 0
    day_cursor = today
    attempt_days_set = set(attempt_days)
    while day_cursor in attempt_days_set:
        current_streak += 1
        day_cursor = day_cursor - timedelta(days=1)

    longest_streak = 0
    streak = 0
    previous_day = None
    for day in attempt_days:
        if previous_day is None or day == previous_day + timedelta(days=1):
            streak += 1
        else:
            streak = 1
        longest_streak = max(longest_streak, streak)
        previous_day = day

    return DashboardLearnerOverviewResponse(
        total_trainings=total_trainings,
        completed_trainings=completed_trainings,
        completed_percent=completed_percent,
        total_tests=len(tests),
        attempts_count=len(attempts),
        best_result=build_result_item(best_result),
        worst_result=build_result_item(worst_result),
        attempts_last_7_days=attempts_last_7_days,
        avg_score_last_7_days=(sum(scores_last_7_days) / len(scores_last_7_days)) if scores_last_7_days else 0.0,
        current_streak_days=current_streak,
        longest_streak_days=longest_streak,
        daily_progress=daily_points,
    )

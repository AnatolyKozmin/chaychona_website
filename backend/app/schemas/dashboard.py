from datetime import datetime

from pydantic import BaseModel


class DashboardProductStat(BaseModel):
    bucket: str
    items_count: int


class DashboardRestaurantStat(BaseModel):
    restaurant_id: str
    restaurant_name: str
    tests_count: int
    learners_count: int


class DashboardTopResultItem(BaseModel):
    user_id: str
    user_name: str
    user_email: str
    attempts_count: int
    avg_score_percent: float
    best_score_percent: float
    last_attempt_at: datetime | None


class DashboardOverviewResponse(BaseModel):
    tests_created_total: int
    products_total: int
    attempts_day: int
    attempts_week: int
    attempts_month: int
    products_by_bucket: list[DashboardProductStat]
    restaurants: list[DashboardRestaurantStat]
    top_results: list[DashboardTopResultItem]


class DashboardLearnerResultItem(BaseModel):
    test_id: int
    test_title: str
    score_percent: float
    finished_at: datetime


class DashboardLearnerOverviewResponse(BaseModel):
    total_trainings: int
    completed_trainings: int
    completed_percent: float
    total_tests: int
    attempts_count: int
    best_result: DashboardLearnerResultItem | None
    worst_result: DashboardLearnerResultItem | None
    attempts_last_7_days: int
    avg_score_last_7_days: float
    current_streak_days: int
    longest_streak_days: int
    daily_progress: list["DashboardLearnerDailyPoint"]


class DashboardLearnerDailyPoint(BaseModel):
    date: str
    attempts: int
    avg_score_percent: float


DashboardLearnerOverviewResponse.model_rebuild()

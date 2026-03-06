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

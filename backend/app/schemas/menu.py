from datetime import datetime

from pydantic import BaseModel, Field


class MenuCategoryPublic(BaseModel):
    id: int
    name: str
    restaurant_id: str | None = None
    branch_id: int | None = None
    menu_type: str | None


class MenuCategoryAdminPublic(MenuCategoryPublic):
    description: str | None
    is_active: bool


class MenuCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    restaurant_id: str | None = None
    branch_id: int | None = None
    menu_type: str | None = Field(default=None, max_length=32)
    description: str | None = Field(default=None, max_length=5000)
    is_active: bool = True


class MenuBranchPublic(BaseModel):
    id: int
    name: str
    is_active: bool
    sort_order: int


class MenuBranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10000)


class MenuDishCard(BaseModel):
    id: int
    name: str
    ingredients: str | None
    # Пусто = шеф ещё не заполнил. Официанту в этом случае блок не показываем.
    allergens: str | None
    description: str | None
    price: int
    price_rubles: str | None
    category: MenuCategoryPublic | None
    image_url: str | None
    video_url: str | None
    audio_url: str | None


class MenuDishAdminPublic(BaseModel):
    id: int
    name: str
    ingredients: str | None
    allergens: str | None
    description: str | None
    price: int
    price_rubles: str | None
    restaurant_id: str | None
    category_id: int | None
    category: MenuCategoryPublic | None
    is_available: bool
    is_active: bool
    photo_dish_path: str | None
    photo_ingredients_path: str | None
    audio_path: str | None
    video_path: str | None
    video_job_queued: bool = False  # видео поставлено на пересборку (сменили фото/озвучку)


class MenuDishCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    ingredients: str | None = Field(default=None, max_length=10000)
    allergens: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=10000)
    price: int = Field(default=0, ge=0)
    price_rubles: str | None = Field(default=None, max_length=32)
    restaurant_id: str | None = None
    category_id: int | None = None
    is_available: bool = True
    is_active: bool = True
    photo_dish_path: str | None = Field(default=None, max_length=1024)
    photo_ingredients_path: str | None = Field(default=None, max_length=1024)
    audio_path: str | None = Field(default=None, max_length=1024)
    video_path: str | None = Field(default=None, max_length=1024)


class MenuRestaurantPublic(BaseModel):
    id: str
    name: str


class MenuFeedResponse(BaseModel):
    total: int
    items: list[MenuDishCard]


class MenuMediaUploadResponse(BaseModel):
    path: str


class MenuDishJobPublic(BaseModel):
    id: int
    dish_id: int
    dish_name: str | None = None
    kind: str = "video"  # image | audio | video
    status: str
    error: str | None = None
    attempts: int
    video_path: str | None = None
    created_at: datetime
    updated_at: datetime


class MenuDishJobsSummary(BaseModel):
    pending: int
    processing: int
    done: int
    error: int
    total: int
    jobs: list[MenuDishJobPublic]


class MenuDishImportJobResponse(BaseModel):
    dish: MenuDishAdminPublic
    job: MenuDishJobPublic | None = None


class GenerateVideosRequest(BaseModel):
    force: bool = False  # пересоздавать видео даже если оно уже есть
    restaurant_id: str | None = None
    category_id: int | None = None
    dish_ids: list[int] | None = None  # если задан — только эти блюда


class GenerateVideosResponse(BaseModel):
    total_considered: int
    enqueued: int
    skipped_no_media: int
    skipped_has_video: int
    skipped_already_queued: int


class MenuImportRowPublic(BaseModel):
    row_number: int
    dish_name: str | None
    category_name: str | None
    dish_id: int | None
    status: str  # created | updated | skipped | error
    error: str | None


class MenuImportSessionPublic(BaseModel):
    id: int
    file_name: str
    restaurant_id: str | None
    restaurant_name: str | None = None
    status: str  # running | done | error
    error: str | None = None
    total_rows: int
    created_dishes: int
    updated_dishes: int
    failed_rows: int
    generate_image: bool
    generate_audio: bool
    generate_video: bool
    created_at: datetime
    finished_at: datetime | None = None
    # Прогресс генерации по этой сессии: сколько заданий в каком состоянии.
    jobs_total: int = 0
    jobs_pending: int = 0
    jobs_processing: int = 0
    jobs_done: int = 0
    jobs_error: int = 0


class MenuImportSessionDetail(MenuImportSessionPublic):
    rows: list[MenuImportRowPublic] = []
    failed_jobs: list[MenuDishJobPublic] = []


class MenuImportPreviewRow(BaseModel):
    row_number: int
    name: str
    category: str | None
    ingredients: str | None
    description: str | None
    has_photo_dish: bool
    has_photo_ingredients: bool
    has_audio: bool
    exists: bool  # блюдо с таким именем уже есть в этом ресторане


class MenuImportPreview(BaseModel):
    """Ответ dry-run: что заедет, если нажать «Загрузить»."""

    file_name: str
    total_rows: int
    will_create: int
    will_update: int
    new_categories: list[str]
    will_generate_images: int
    will_generate_audio: int
    will_generate_videos: int
    rows: list[MenuImportPreviewRow]


class MenuImportResult(BaseModel):
    """Ответ на залив файла: либо только план (dry-run), либо готовая сессия."""

    dry_run: bool
    preview: MenuImportPreview | None = None
    session: MenuImportSessionDetail | None = None
    # Чего не хватает серверу под заказанную генерацию: ключей провайдеров.
    # Заливу не мешает, но показать надо сразу, а не через упавшие задания.
    warnings: list[str] = []

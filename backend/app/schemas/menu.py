from pydantic import BaseModel, Field


class MenuCategoryPublic(BaseModel):
    id: int
    name: str
    menu_type: str | None


class MenuCategoryAdminPublic(MenuCategoryPublic):
    description: str | None
    is_active: bool


class MenuCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    menu_type: str | None = Field(default=None, max_length=32)
    description: str | None = Field(default=None, max_length=5000)
    is_active: bool = True


class MenuDishCard(BaseModel):
    id: int
    name: str
    ingredients: str | None
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


class MenuDishCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    ingredients: str | None = Field(default=None, max_length=10000)
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


class MenuFeedResponse(BaseModel):
    total: int
    items: list[MenuDishCard]


class MenuMediaUploadResponse(BaseModel):
    path: str

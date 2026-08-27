"""Что именно ставится в очередь по строке реестра.

Проверяем решающую матрицу: генерим только недостающее, а видео ждёт свои
исходники в `blocked`, если они ещё не приехали. БД не нужна — сессия заглушка.
"""
from app.models.menu import MenuDish, MenuDishMediaJob
from app.services.menu_import import ParsedRow
from app.services.menu_import_runner import _enqueue_generation


class RecordingSession:
    """Заглушка Session, которая просто копит всё, что в неё добавили."""

    def __init__(self):
        self.added: list[MenuDishMediaJob] = []

    def add(self, obj):
        self.added.append(obj)


def _dish(**kwargs):
    dish = MenuDish(name="Плов")
    dish.id = 10
    for key, value in kwargs.items():
        setattr(dish, key, value)
    return dish


def _row(**kwargs):
    defaults = {
        "row_number": 2,
        "name": "Плов",
        "ingredients": "рис, баранина",
        "description": "Рассказ про плов",
    }
    defaults.update(kwargs)
    return ParsedRow(**defaults)


def enqueue(dish, row=None, **flags):
    db = RecordingSession()
    options = {"generate_image": True, "generate_audio": True, "generate_video": True}
    options.update(flags)
    _enqueue_generation(db, dish=dish, row=row or _row(), session_id=1, **options)
    return {job.kind: job for job in db.added}


def test_empty_dish_gets_all_three_stages():
    jobs = enqueue(_dish())

    assert set(jobs) == {"image", "audio", "video"}
    # Картинки и озвучки ещё нет — видео обязано ждать.
    assert jobs["video"].status == "blocked"
    assert jobs["image"].status == "pending"
    assert jobs["audio"].status == "pending"


def test_image_from_archive_is_not_regenerated():
    """За то, что заказчик уже прислал, провайдеру платить не за что."""
    jobs = enqueue(_dish(photo_ingredients_path="uploads/i.png"))

    assert "image" not in jobs
    assert "audio" in jobs


def test_audio_from_archive_is_not_regenerated():
    jobs = enqueue(_dish(audio_path="uploads/a.mp3"))

    assert "audio" not in jobs
    assert "image" in jobs


def test_ready_dish_goes_straight_to_video():
    jobs = enqueue(_dish(photo_ingredients_path="uploads/i.png", audio_path="uploads/a.mp3"))

    assert set(jobs) == {"video"}
    assert jobs["video"].status == "pending"


def test_prompt_is_built_from_dish_and_ingredients():
    jobs = enqueue(_dish())

    assert "Плов" in jobs["image"].prompt
    assert "рис, баранина" in jobs["image"].prompt


def test_voice_text_comes_from_the_voiceover_column():
    jobs = enqueue(_dish())

    assert jobs["audio"].prompt == "Рассказ про плов"


def test_voice_text_falls_back_to_ingredients():
    """Пустая колонка озвучки — не повод молчать: читаем хотя бы состав."""
    jobs = enqueue(_dish(), row=_row(description=None))

    assert jobs["audio"].prompt == "рис, баранина"


def test_nothing_to_say_means_no_audio_job():
    jobs = enqueue(_dish(), row=_row(description=None, ingredients=None))

    assert "audio" not in jobs
    # И видео тогда не соберётся — ставить его бессмысленно.
    assert "video" not in jobs


def test_dish_photo_stands_in_for_missing_ingredients_photo():
    """Видео можно собрать и по фото блюда, если картинки ингредиентов не будет."""
    jobs = enqueue(_dish(photo_dish_path="uploads/d.png", audio_path="uploads/a.mp3"), generate_image=False)

    assert set(jobs) == {"video"}
    assert jobs["video"].status == "pending"


def test_video_switched_off_leaves_only_generation():
    jobs = enqueue(_dish(), generate_video=False)

    assert set(jobs) == {"image", "audio"}


def test_generation_switched_off_still_composes_ready_media():
    jobs = enqueue(
        _dish(photo_ingredients_path="uploads/i.png", audio_path="uploads/a.mp3"),
        generate_image=False,
        generate_audio=False,
    )

    assert set(jobs) == {"video"}


def test_all_switches_off_enqueues_nothing():
    jobs = enqueue(_dish(), generate_image=False, generate_audio=False, generate_video=False)

    assert jobs == {}


def test_video_blocked_while_only_audio_is_pending():
    jobs = enqueue(_dish(photo_ingredients_path="uploads/i.png"))

    assert jobs["video"].status == "blocked"


def test_jobs_carry_the_session():
    jobs = enqueue(_dish())

    assert {job.session_id for job in jobs.values()} == {1}

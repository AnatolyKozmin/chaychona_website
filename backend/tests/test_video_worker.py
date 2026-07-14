"""Юнит-тесты веток обработки задания воркером.

Работаем с transient ORM-объектами и фейковой сессией — БД и ffmpeg не нужны
(compose и разрешение путей замоканы)."""
from pathlib import Path

import app.services.video_worker as vw
from app.models.menu import MenuDish, MenuDishVideoJob


class FakeSession:
    """Мини-заглушка Session: только .get() и .commit(), которые нужны _process_job."""

    def __init__(self, objs):
        self._objs = objs
        self.commits = 0

    def get(self, model, pk):
        return self._objs.get((model, pk))

    def commit(self):
        self.commits += 1


def _make(**dish_kwargs):
    dish = MenuDish(name="Плов")
    dish.id = 10
    for key, value in dish_kwargs.items():
        setattr(dish, key, value)
    job = MenuDishVideoJob()
    job.id = 1
    job.dish_id = 10
    job.status = "processing"
    job.attempts = 1
    return dish, job, FakeSession({(MenuDishVideoJob, 1): job, (MenuDish, 10): dish})


def test_process_job_success(tmp_path, monkeypatch):
    monkeypatch.setattr(vw, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(vw, "resolve_media_abspath", lambda p: Path("x") if p else None)
    calls = {}
    monkeypatch.setattr(
        vw, "compose_still_video", lambda img, aud, out: calls.setdefault("out", out)
    )
    dish, job, db = _make(photo_ingredients_path="uploads/i.jpg", audio_path="uploads/a.mp3")

    vw._process_job(db, 1)

    assert job.status == "done"
    assert job.error is None
    assert dish.video_path.startswith("uploads/")
    assert dish.video_path.endswith(".mp4")
    # видео пишется под UPLOAD_DIR
    assert str(calls["out"]).startswith(str(tmp_path))


def test_process_job_falls_back_to_dish_photo(monkeypatch):
    # нет фото ингредиентов — берётся photo_dish
    seen = {}

    def fake_resolve(p):
        seen["last"] = p
        return Path("x") if p else None

    monkeypatch.setattr(vw, "resolve_media_abspath", fake_resolve)
    monkeypatch.setattr(vw, "compose_still_video", lambda *a: None)
    dish, job, db = _make(
        photo_ingredients_path=None, photo_dish_path="uploads/d.jpg", audio_path="uploads/a.mp3"
    )

    vw._process_job(db, 1)
    assert job.status == "done"


def test_process_job_missing_audio(monkeypatch):
    monkeypatch.setattr(
        vw, "resolve_media_abspath", lambda p: Path("x") if p and "i.jpg" in p else None
    )
    dish, job, db = _make(photo_ingredients_path="uploads/i.jpg", audio_path=None)

    vw._process_job(db, 1)
    assert job.status == "error"
    assert "аудио" in (job.error or "")


def test_process_job_missing_photo(monkeypatch):
    monkeypatch.setattr(vw, "resolve_media_abspath", lambda p: None)
    dish, job, db = _make(photo_ingredients_path=None, photo_dish_path=None, audio_path="uploads/a.mp3")

    vw._process_job(db, 1)
    assert job.status == "error"
    assert "фото" in (job.error or "")


def test_process_job_compose_failure_marks_error(monkeypatch):
    monkeypatch.setattr(vw, "resolve_media_abspath", lambda p: Path("x") if p else None)

    def boom(img, aud, out):
        raise vw.VideoCompositionError("ffmpeg boom")

    monkeypatch.setattr(vw, "compose_still_video", boom)
    dish, job, db = _make(photo_ingredients_path="uploads/i.jpg", audio_path="uploads/a.mp3")

    vw._process_job(db, 1)
    assert job.status == "error"
    assert "ffmpeg boom" in (job.error or "")
    assert dish.video_path is None

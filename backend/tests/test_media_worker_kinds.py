"""Ветки воркера по видам заданий: картинка, озвучка и разблокировка видео.

Без БД и сети: провайдеры и запись файлов замоканы, сессия — заглушка.
"""
import pytest

import app.services.video_worker as vw
from app.models.menu import MenuDish, MenuDishMediaJob
from app.services.generation import GenerationError


class FakeSession:
    """Заглушка Session: get/commit, плюс заранее заданные ответы на запросы."""

    def __init__(self, objs, scalars_result=None, scalar_result=0):
        self._objs = objs
        self._scalars_result = scalars_result or []
        self._scalar_result = scalar_result
        self.commits = 0

    def get(self, model, pk):
        return self._objs.get((model, pk))

    def commit(self):
        self.commits += 1

    def scalars(self, _query):
        return _Result(self._scalars_result)

    def scalar(self, _query):
        return self._scalar_result


class _Result:
    def __init__(self, items):
        self._items = items

    def all(self):
        return list(self._items)


def _job(kind, prompt=None, status="processing", job_id=1):
    job = MenuDishMediaJob()
    job.id = job_id
    job.dish_id = 10
    job.kind = kind
    job.prompt = prompt
    job.status = status
    job.attempts = 1
    return job


def _dish(**kwargs):
    dish = MenuDish(name="Плов")
    dish.id = 10
    for key, value in kwargs.items():
        setattr(dish, key, value)
    return dish


def test_image_job_saves_generated_photo(monkeypatch):
    monkeypatch.setattr(vw, "image_ready", lambda: True)
    monkeypatch.setattr(
        vw, "generate_ingredients_image", lambda prompt: (b"png-bytes", ".png")
    )
    monkeypatch.setattr(vw, "save_upload_bytes", lambda content, ext: f"uploads/new{ext}")
    dish = _dish()
    job = _job("image", prompt="ингредиенты плова")
    db = FakeSession({(MenuDishMediaJob, 1): job, (MenuDish, 10): dish})

    vw._process_image_job(db, job, dish)

    assert job.status == "done"
    assert job.error is None
    assert dish.photo_ingredients_path == "uploads/new.png"


def test_image_job_without_prompt_fails():
    dish = _dish()
    job = _job("image", prompt="   ")
    db = FakeSession({})

    vw._process_image_job(db, job, dish)

    assert job.status == "error"
    assert "промпта" in job.error


def test_image_job_reports_provider_error(monkeypatch):
    """Ключ есть, но провайдер отказал — задание падает с его текстом, а не молча."""
    monkeypatch.setattr(vw, "image_ready", lambda: True)

    def boom(_prompt):
        raise GenerationError("Magnific ответил 402: закончились кредиты")

    monkeypatch.setattr(vw, "generate_ingredients_image", boom)
    dish = _dish()
    job = _job("image", prompt="ингредиенты")
    db = FakeSession({})

    vw._process_image_job(db, job, dish)

    assert job.status == "error"
    assert "кредиты" in job.error
    assert dish.photo_ingredients_path is None


def test_image_job_waits_for_a_key_instead_of_failing(monkeypatch):
    """Без MAGNIFIC_API_KEY картинка ждёт ключа, а не пишет ошибку на каждое блюдо."""
    monkeypatch.setattr(vw, "image_ready", lambda: False)

    def must_not_be_called(prompt):
        raise AssertionError("без ключа к провайдеру не ходим")

    monkeypatch.setattr(vw, "generate_ingredients_image", must_not_be_called)
    dish = _dish()
    job = _job("image", prompt="ингредиенты плова")
    db = FakeSession({})

    vw._process_image_job(db, job, dish)

    assert job.status == vw.WAITING_KEY_STATUS
    assert job.error is None
    assert dish.photo_ingredients_path is None


def test_audio_job_saves_voiceover(monkeypatch):
    monkeypatch.setattr(vw, "tts_mode", lambda: "elevenlabs")
    monkeypatch.setattr(vw, "synthesize_speech", lambda text: (b"mp3-bytes", ".mp3"))
    monkeypatch.setattr(vw, "save_upload_bytes", lambda content, ext: f"uploads/voice{ext}")
    dish = _dish()
    job = _job("audio", prompt="Идеальный набор под крепкие напитки")
    db = FakeSession({})

    vw._process_audio_job(db, job, dish)

    assert job.status == "done"
    assert dish.audio_path == "uploads/voice.mp3"


def test_audio_job_waits_when_no_tts_provider_is_configured(monkeypatch):
    """Без провайдера озвучка не падает: задание ждёт ключа, блюдо покажет заглушку.

    Иначе каждый залив меню оставлял бы сотню «ошибок», которые на самом деле
    означают лишь «озвучку пока никто не делает».
    """
    monkeypatch.setattr(vw, "tts_mode", lambda: vw.TTS_STUB)
    dish = _dish()
    job = _job("audio", prompt="Идеальный набор под крепкие напитки")
    db = FakeSession({})

    vw._process_audio_job(db, job, dish)

    assert job.status == vw.WAITING_KEY_STATUS
    assert job.error is None
    assert dish.audio_path is None


def test_waiting_audio_keeps_video_blocked():
    """Видео ждёт отложенную озвучку, а не закрывается ошибкой.

    `_release_video_jobs` закрывает видео, когда смежные стадии «доработали»;
    отложенная озвучка доработавшей не считается, иначе каждое блюдо из залива
    без TTS получало бы ошибку по видео.
    """
    dish = _dish(photo_ingredients_path="uploads/plov.png")  # озвучки нет
    video = _job("video", status="blocked", job_id=2)
    db = FakeSession(
        {(MenuDish, 10): dish},
        scalars_result=[video],
        scalar_result=1,  # одно незакрытое смежное задание — та самая озвучка
    )

    vw._release_video_jobs(db, dish.id)

    assert video.status == "blocked"
    assert video.error is None


def test_audio_job_without_text_fails():
    dish = _dish()
    job = _job("audio", prompt=None)
    db = FakeSession({})

    vw._process_audio_job(db, job, dish)

    assert job.status == "error"
    assert "текста" in job.error


def test_unknown_kind_fails_loudly():
    dish = _dish()
    job = _job("hologram")
    db = FakeSession({(MenuDishMediaJob, 1): job, (MenuDish, 10): dish})

    vw._process_job(db, 1)

    assert job.status == "error"
    assert "Неизвестный вид" in job.error


def test_blocked_video_starts_once_media_is_ready():
    video = _job("video", status="blocked", job_id=2)
    dish = _dish(photo_ingredients_path="uploads/i.png", audio_path="uploads/a.mp3")
    db = FakeSession({(MenuDish, 10): dish}, scalars_result=[video], scalar_result=0)

    vw._release_video_jobs(db, 10)

    assert video.status == "pending"


def test_blocked_video_keeps_waiting_while_stages_run():
    video = _job("video", status="blocked", job_id=2)
    dish = _dish()  # исходников ещё нет
    db = FakeSession({(MenuDish, 10): dish}, scalars_result=[video], scalar_result=1)

    vw._release_video_jobs(db, 10)

    assert video.status == "blocked"


def test_blocked_video_fails_when_stages_gave_up():
    """Картинка и озвучка отработали, а файлов нет — видео не должно висеть вечно."""
    video = _job("video", status="blocked", job_id=2)
    dish = _dish()
    db = FakeSession({(MenuDish, 10): dish}, scalars_result=[video], scalar_result=0)

    vw._release_video_jobs(db, 10)

    assert video.status == "error"
    assert "Не дождались" in video.error


def test_release_is_a_noop_without_blocked_jobs():
    db = FakeSession({}, scalars_result=[])

    vw._release_video_jobs(db, 10)

    assert db.commits == 0

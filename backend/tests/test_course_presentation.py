"""Резка PDF-презентации на слайды: сервис и ручка заливки.

Тесты сервиса базы не требуют — PDF собирается прямо здесь, а каталог загрузок
подменяется на временный, чтобы прогон не сыпал мусор в media_uploads.
"""
import io

import pytest
from PIL import Image

from app.services import media, presentation
from app.services.presentation import PresentationError, render_pdf


@pytest.fixture(autouse=True)
def temp_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "UPLOAD_DIR", tmp_path / "uploads")
    return tmp_path / "uploads"


def make_pdf(pages: int = 3, size: tuple[int, int] = (1600, 900)) -> bytes:
    """Собрать PDF из цветных страниц — этого хватает, чтобы проверить рендер."""
    colors = ["white", "red", "blue", "green", "black"]
    images = [Image.new("RGB", size, colors[i % len(colors)]) for i in range(pages)]
    buffer = io.BytesIO()
    images[0].save(buffer, format="PDF", save_all=True, append_images=images[1:])
    return buffer.getvalue()


def test_render_pdf_splits_pages_in_order(temp_uploads):
    slides = render_pdf(make_pdf(pages=3))

    assert [slide.sort_order for slide in slides] == [0, 1, 2]
    for slide in slides:
        assert slide.image_path.startswith("uploads/")
        assert slide.image_path.endswith(".jpg")
        saved = temp_uploads / slide.image_path.split("/", 1)[1]
        assert saved.exists()
        with Image.open(saved) as image:
            assert image.format == "JPEG"
            assert (image.width, image.height) == (slide.width, slide.height)


def test_render_pdf_uses_target_width():
    slides = render_pdf(make_pdf(pages=1, size=(1024, 768)), target_width=800)

    # Ширина задаётся целевой, пропорции страницы сохраняются.
    assert slides[0].width == pytest.approx(800, abs=2)
    assert slides[0].height == pytest.approx(600, abs=2)


def test_default_width_keeps_small_text_readable_on_zoom():
    """Ширина по умолчанию — не украшательство, а требование к читаемости.

    Официант читает сноски 9-12 пт с телефона на увеличении ~260%; на 1600 px
    в этом режиме буквы мылит. Если значение соберутся уменьшать, пусть сначала
    посмотрят на слайд глазами.
    """
    assert presentation.TARGET_WIDTH_PX >= 2000

    slides = render_pdf(make_pdf(pages=1, size=(1600, 900)))
    assert slides[0].width >= 2000


def test_heavy_slide_is_compressed_harder(temp_uploads):
    """Слайд-фотография не должна уезжать на телефон почти мегабайтом."""
    noise = Image.effect_noise((3200, 1800), 90).convert("RGB")
    buffer = io.BytesIO()
    noise.save(buffer, format="PDF", resolution=240.0)

    slides = render_pdf(buffer.getvalue())
    saved = temp_uploads / slides[0].image_path.split("/", 1)[1]
    # Порог с запасом: шум сжимается хуже любой реальной фотографии.
    assert saved.stat().st_size < presentation.SIZE_SOFT_LIMIT_BYTES * 1.5


def test_light_slide_keeps_full_quality(temp_uploads, monkeypatch):
    """Текстовые слайды в предел не упираются и пережиматься не должны."""
    calls: list[int] = []
    original = presentation._encode_at

    def spy(image, quality):
        calls.append(quality)
        return original(image, quality)

    monkeypatch.setattr(presentation, "_encode_at", spy)
    render_pdf(make_pdf(pages=1))

    assert calls == [presentation.JPEG_QUALITY]


def test_render_pdf_rejects_empty_file():
    with pytest.raises(PresentationError, match="пустой"):
        render_pdf(b"")


def test_render_pdf_rejects_not_a_pdf():
    with pytest.raises(PresentationError, match="Не удалось прочитать PDF"):
        render_pdf(b"\x89PNG\r\n\x1a\n and some bytes that are definitely not a pdf")


def test_render_pdf_rejects_too_many_pages(monkeypatch):
    # Книгу вместо презентации заливать нельзя: и рендер, и листание на телефоне
    # станут неподъёмными.
    monkeypatch.setattr(presentation, "MAX_SLIDES", 2)

    with pytest.raises(PresentationError, match="максимум"):
        render_pdf(make_pdf(pages=3))


@pytest.mark.parametrize(
    "width_pt, target, expected",
    [
        (720.0, 1600, 1600 / 720.0),  # обычный слайд — ровно под целевую ширину
        (0.0, 1600, 1.0),  # битая страница без размеров — рендерим как есть
        (10.0, 1600, 4.0),  # микроскопическая страница упирается в верхний предел
        (100000.0, 1600, 0.5),  # гигантская — в нижний, иначе получим мыло
    ],
)
def test_scale_stays_within_bounds(width_pt, target, expected):
    assert presentation._scale_for(width_pt, target) == pytest.approx(expected)


def test_upload_presentation_rejects_non_pdf(client, auth_headers):
    response = client.post(
        "/api/v1/courses/admin/presentation",
        headers=auth_headers,
        files={"file": ("deck.pptx", b"whatever", "application/vnd.ms-powerpoint")},
    )

    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_upload_presentation_returns_slides(client, auth_headers, temp_uploads):
    response = client.post(
        "/api/v1/courses/admin/presentation",
        headers=auth_headers,
        files={"file": ("deck.pdf", make_pdf(pages=2), "application/pdf")},
    )

    assert response.status_code == 201, response.text
    slides = response.json()["slides"]
    assert len(slides) == 2
    assert [slide["sort_order"] for slide in slides] == [0, 1]
    assert slides[0]["image_url"].startswith("/api/v1/menu/media?path=uploads/")
    assert slides[0]["width"] > 0 and slides[0]["height"] > 0


def test_upload_presentation_requires_auth(client):
    response = client.post(
        "/api/v1/courses/admin/presentation",
        files={"file": ("deck.pdf", make_pdf(pages=1), "application/pdf")},
    )

    assert response.status_code in (401, 403)

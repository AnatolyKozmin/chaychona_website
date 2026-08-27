"""Разбор PDF-презентации на слайды-картинки.

Отдавать сотруднику сам PDF нельзя: стандарт открывают с телефона, а мобильные
браузеры либо тянут тяжёлый рендерер, либо передают файл во внешнюю читалку —
и человек выпадает из обучения вместе с прогрессом. Поэтому презентация режется
один раз при заливке, а на телефон приезжают готовые картинки: их листают тем
же свайпом, что и обычные блоки стандарта, и кэширует тот же `GET /menu/media`.

Рендерит pypdfium2: колёса самодостаточные, в образ не надо ставить ни poppler,
ни LibreOffice. Отсюда же и ограничение на формат — только PDF; .pptx требует
LibreOffice в контейнере и молча портит вёрстку на нестандартных шрифтах.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass

import pypdfium2 as pdfium
from PIL import Image

from app.services.media import save_upload_bytes

logger = logging.getLogger(__name__)

# Больше — почти наверняка залили не презентацию, а книгу: и рендер, и листание
# на телефоне станут неподъёмными.
MAX_SLIDES = 300

# Ширина слайда в пикселях. Считана от худшего случая: сноска 9-12 пт на слайде
# 13.3", которую официант читает с телефона на зуме ~260%. На 1600 px в этом
# режиме буквы уже мылит, на 2000 — чисто; дальше прирост резкости почти не
# виден, а вес растёт. Текстовый слайд такого размера — 50-150 КБ, слайд с
# фотографией во всю площадь — до ~600 КБ (см. SIZE_SOFT_LIMIT_BYTES ниже).
TARGET_WIDTH_PX = 2000
JPEG_QUALITY = 82

# Слайд с фотографией во всю площадь на 2000 px тянет под мегабайт, а официант
# смотрит колоду с телефона по мобильной сети. Такие слайды (и только их —
# текстовые в предел не упираются) пережимаем сильнее: на фотографии разница
# между 82 и 70 глазом не ловится, а вес падает вдвое.
SIZE_SOFT_LIMIT_BYTES = 600 * 1024
JPEG_QUALITY_HEAVY = 70

# scale=1 у pdfium — это 72 dpi. Верхняя граница держит вес слайда в узде,
# нижняя не даёт получить мыло из нестандартно мелкой страницы.
_MIN_SCALE = 0.5
_MAX_SCALE = 4.0


class PresentationError(RuntimeError):
    """PDF не читается или не годится в презентацию."""


@dataclass(frozen=True)
class RenderedSlide:
    """Готовый слайд: путь в хранилище медиа и размеры картинки."""

    image_path: str
    width: int
    height: int
    sort_order: int


def render_pdf(content: bytes, *, target_width: int = TARGET_WIDTH_PX) -> list[RenderedSlide]:
    """Разрезать PDF на слайды и сложить картинки в хранилище медиа.

    Возвращает слайды в порядке страниц. Файлы уже лежат в `uploads/`, поэтому
    вызывающий обязан либо привязать их к блоку, либо смириться с сиротами:
    чистки хранилища в проекте нет (её нет и для остальных загрузок).
    """
    if not content:
        raise PresentationError("Файл презентации пустой")

    try:
        document = pdfium.PdfDocument(content)
    except Exception as exc:  # pdfium кидает свои типы ошибок на битый файл и на пароль
        raise PresentationError(
            f"Не удалось прочитать PDF: {exc}. Файл повреждён или защищён паролем."
        ) from exc

    try:
        page_count = len(document)
        if page_count == 0:
            raise PresentationError("В PDF нет ни одной страницы")
        if page_count > MAX_SLIDES:
            raise PresentationError(
                f"В презентации {page_count} страниц, а максимум — {MAX_SLIDES}. "
                "Разбейте её на несколько стандартов."
            )

        slides: list[RenderedSlide] = []
        for index in range(page_count):
            page = document[index]
            try:
                slides.append(_render_page(page, index, target_width))
            except PresentationError:
                raise
            except Exception as exc:
                raise PresentationError(f"Страница {index + 1} не отрисовалась: {exc}") from exc
            finally:
                page.close()
        logger.info("Презентация разрезана на %s слайдов", len(slides))
        return slides
    finally:
        document.close()


def _render_page(page, index: int, target_width: int) -> RenderedSlide:
    width_pt, _height_pt = page.get_size()
    bitmap = page.render(scale=_scale_for(width_pt, target_width))
    try:
        image = bitmap.to_pil()
    finally:
        bitmap.close()

    if image.mode != "RGB":
        # У слайдов бывает прозрачный фон; без белой подложки JPEG сделает его чёрным.
        flat = Image.new("RGB", image.size, "white")
        flat.paste(image, mask=image.getchannel("A") if "A" in image.getbands() else None)
        image = flat

    return RenderedSlide(
        image_path=save_upload_bytes(_encode(image), ".jpg"),
        width=image.width,
        height=image.height,
        sort_order=index,
    )


def _encode(image: Image.Image) -> bytes:
    """Слайд в jpeg, с более сильным сжатием для тяжёлых (фотографических) страниц."""
    data = _encode_at(image, JPEG_QUALITY)
    if len(data) <= SIZE_SOFT_LIMIT_BYTES:
        return data
    lighter = _encode_at(image, JPEG_QUALITY_HEAVY)
    logger.info(
        "Тяжёлый слайд пережат: %.0f КБ -> %.0f КБ", len(data) / 1024, len(lighter) / 1024
    )
    return lighter if len(lighter) < len(data) else data


def _encode_at(image: Image.Image, quality: int) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buffer.getvalue()


def _scale_for(width_pt: float, target_width: int) -> float:
    if width_pt <= 0:
        return 1.0
    return max(_MIN_SCALE, min(target_width / width_pt, _MAX_SCALE))

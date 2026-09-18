"""Разбор «Вкусной тетради» в формате Word — того файла, который ведёт шеф.

В отличие от Excel-реестра, тут нет ни одной колонки с путями: фотографии
лежат прямо в ячейках рядом с названиями, и вынимаем мы их из самого .docx
(это zip, картинки внутри — `word/media/*`). Поэтому результат разбора — тот же
`ParsedRegistry`, только архивом служит сам документ, а «путь к файлу» в строке
это имя картинки внутри него.

Вёрстка таблиц в документе неоднородная, и это не случайность: у соусов и суши
человеку удобнее плитка, а не таблица «блюдо в строке». Встречается четыре вида:

    обычная       | Блюдо + фото | Состав | Красочное описание |
    перевёрнутая  | Соус А | Соус Б | Соус В |     ← имена и фото в первой строке
                  | состав | состав | состав |     ← состав во второй
    плитка        | Калифорния \n состав | Филадельфия \n состав |   (одна строка)
    только имена  | Варенье кизил | Варенье абрикос |                (без состава)

Определяем вид не по номеру таблицы, а по тому, где лежат картинки и как
заполнены ячейки: файл правят руками, и любая привязка к порядку таблиц
развалится на следующей версии документа.

Заголовки между таблицами дают два уровня: кухня («Восточная кухня») и раздел
(«Салаты»). Раздел с одним и тем же именем есть в обеих кухнях, поэтому кухню
тащим отдельным полем — иначе «Салаты» схлопнутся в одну категорию.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path, PurePosixPath

import docx
from docx.document import Document as DocxDocument
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from app.services.menu_import import ParsedRegistry, ParsedRow, RegistryParseError

_BLIP_TAG = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
_EMBED_ATTR = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"

# Служебные строки документа: заголовок тетради и время приготовления раздела.
_SKIP_PREFIXES = ("время приготовл",)
_TITLE_MARKERS = ("вкусная тетрадь",)

# Подпись перед перечнем продуктов — в состав блюда её тащить незачем.
_INGREDIENTS_LABELS = ("основные ингредиенты:", "основные ингредиенты")

# Ячейка-заголовок таблицы: такие строки не блюда.
_HEADER_WORDS = {"блюдо", "состав", "красочное описание", "описание", "ингредиенты"}

# Имя блюда длиннее — почти наверняка в ячейку попало описание.
_NAME_SANITY_LIMIT = 120


def _text(cell: _Cell) -> str:
    """Текст ячейки без пустых строк по краям."""
    lines = [" ".join(line.split()) for line in cell.text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _images(cell: _Cell, doc: DocxDocument) -> list[str]:
    """Пути картинок ячейки внутри .docx (`word/media/imageN.png`)."""
    paths: list[str] = []
    part = doc.part
    for blip in cell._tc.iter(_BLIP_TAG):
        rel_id = blip.get(_EMBED_ATTR)
        related = part.related_parts.get(rel_id) if rel_id else None
        if related is None:
            continue
        paths.append(str(related.partname).lstrip("/"))
    return paths


def _strip_label(value: str) -> str:
    """Убрать подпись «Основные ингредиенты:» из начала состава."""
    text = value.strip()
    lowered = text.lower()
    for label in _INGREDIENTS_LABELS:
        if lowered.startswith(label):
            return text[len(label) :].strip(" :\n")
    return text


def _flat(value: str) -> str | None:
    """Многострочная ячейка → одна строка; пустое — None."""
    text = " ".join(value.split())
    return text or None


def _is_header_row(texts: list[str]) -> bool:
    filled = [t.strip().lower() for t in texts if t.strip()]
    return bool(filled) and all(t in _HEADER_WORDS for t in filled)


def _looks_like_tiles(row_texts: list[str]) -> bool:
    """Строка таблицы — плитка из самостоятельных блюд, а не «блюдо и его состав»."""
    filled = [t for t in row_texts if t]
    if len(filled) < 2:
        return False
    for cell_text in filled:
        head = cell_text.splitlines()[0]
        if not _looks_like_name(head):
            return False
    return True


def _looks_like_name(text: str) -> bool:
    """Похоже на название блюда, а не на состав или описание."""
    if not text or "\n" in text:
        return False
    lowered = text.lower()
    if any(label in lowered for label in _INGREDIENTS_LABELS):
        return False
    return len(text) <= _NAME_SANITY_LIMIT


class _RowBuilder:
    """Накапливает разобранные блюда, продолжая сквозную нумерацию строк."""

    def __init__(self) -> None:
        self.rows: list[ParsedRow] = []

    def add(
        self,
        *,
        name: str,
        branch: str | None,
        category: str | None,
        ingredients: str | None,
        description: str | None,
        photo: str | None,
        note: str | None,
    ) -> None:
        clean_name = " ".join(name.split())
        if not clean_name:
            return
        notes = [note] if note else []
        if len(clean_name) > _NAME_SANITY_LIMIT:
            # Режем, но обязательно помечаем: скорее всего, вёрстка ячейки
            # уехала и в название попал кусок описания.
            clean_name = clean_name[:_NAME_SANITY_LIMIT].rstrip()
            notes.append("название слишком длинное — проверьте, не описание ли это")
        if not ingredients and not description:
            notes.append("нет ни состава, ни описания")
        self.rows.append(
            ParsedRow(
                row_number=len(self.rows) + 1,
                name=clean_name,
                branch=branch,
                category=category,
                ingredients=ingredients,
                description=description,
                photo_dish=photo,
                note="; ".join(notes) or None,
            )
        )


def _dedupe_columns(row) -> list[_Cell]:
    """Ячейки строки без повторов от объединённых колонок.

    Word отдаёт объединённую ячейку столько раз, сколько колонок она занимает;
    в документе шефа так свёрстан «Мангал» — пять колонок, из них три копии.
    Дубли режем и по самой ячейке, и по совпадению текста подряд: встречается
    и то, и другое.
    """
    cells: list[_Cell] = []
    seen_tc: set[int] = set()
    for cell in row.cells:
        marker = id(cell._tc)
        if marker in seen_tc:
            continue
        seen_tc.add(marker)
        if cells and _text(cells[-1]) == _text(cell) and _text(cell):
            continue
        cells.append(cell)
    return cells


def _parse_table(
    table: Table,
    doc: DocxDocument,
    builder: _RowBuilder,
    *,
    branch: str | None,
    category: str | None,
) -> None:
    grid = [_dedupe_columns(row) for row in table.rows]
    grid = [cells for cells in grid if cells]
    if not grid:
        return

    texts = [[_text(cell) for cell in cells] for cells in grid]
    images = [[_images(cell, doc) for cell in cells] for cells in grid]

    start = 1 if _is_header_row(texts[0]) else 0

    # Плитка: вся таблица — одна строка, в каждой ячейке своё блюдо.
    # Но однострочной бывает и обычная таблица «блюдо | состав | описание»,
    # поэтому требуем, чтобы каждая ячейка начиналась с собственного названия:
    # ячейка с «Основные ингредиенты:» — это состав соседнего блюда, а не блюдо.
    if len(grid) - start == 1 and len(grid[start]) > 1 and _looks_like_tiles(texts[start]):
        _parse_tiles(texts[start], images[start], builder, branch=branch, category=category)
        return

    index = start
    while index < len(grid):
        row_texts = texts[index]
        row_images = images[index]
        filled = [t for t in row_texts if t]

        # Перевёрнутая таблица: имена (и фото) в строке, состав — под ними.
        columns_with_images = sum(1 for imgs in row_images if imgs)
        names_row = len(filled) > 1 and all(_looks_like_name(t) for t in filled)
        if index + 1 < len(grid) and (columns_with_images > 1 or names_row):
            below = texts[index + 1]
            if not any(images[index + 1]) and any(below):
                _parse_transposed(
                    row_texts, row_images, below, builder, branch=branch, category=category
                )
                index += 2
                continue

        _parse_plain_row(row_texts, row_images, builder, branch=branch, category=category)
        index += 1


def _parse_tiles(
    row_texts: list[str],
    row_images: list[list[str]],
    builder: _RowBuilder,
    *,
    branch: str | None,
    category: str | None,
) -> None:
    """Плитка: в ячейке название первой строкой, остальное — состав."""
    for cell_text, imgs in zip(row_texts, row_images):
        if not cell_text:
            continue
        lines = cell_text.splitlines()
        builder.add(
            name=lines[0],
            branch=branch,
            category=category,
            ingredients=_flat(_strip_label("\n".join(lines[1:]))),
            description=None,
            photo=imgs[0] if imgs else None,
            note=None,
        )


def _parse_transposed(
    names: list[str],
    name_images: list[list[str]],
    below: list[str],
    builder: _RowBuilder,
    *,
    branch: str | None,
    category: str | None,
) -> None:
    """Имена в верхней строке, состав — ровно под каждым именем."""
    for column, name in enumerate(names):
        if not name:
            continue
        imgs = name_images[column] if column < len(name_images) else []
        under = below[column] if column < len(below) else ""
        builder.add(
            name=name.splitlines()[0],
            branch=branch,
            category=category,
            ingredients=_flat(_strip_label(under)),
            description=None,
            photo=imgs[0] if imgs else None,
            note="разобрано как таблица «имена сверху, состав снизу»",
        )


def _parse_plain_row(
    row_texts: list[str],
    row_images: list[list[str]],
    builder: _RowBuilder,
    *,
    branch: str | None,
    category: str | None,
) -> None:
    """Обычная строка: название и фото в первой ячейке, дальше состав и описание."""
    if not row_texts or not row_texts[0]:
        return
    first = row_texts[0].splitlines()
    name = first[0]
    tail = _flat(_strip_label("\n".join(first[1:])))
    ingredients = _flat(_strip_label(row_texts[1])) if len(row_texts) > 1 else None
    description = _flat(row_texts[2]) if len(row_texts) > 2 else None
    if ingredients is None and tail:
        # Состав уехал в ячейку с названием — так свёрстаны «Гарниры».
        ingredients = tail
    photos = row_images[0] if row_images else []
    builder.add(
        name=name,
        branch=branch,
        category=category,
        ingredients=ingredients,
        description=description,
        photo=photos[0] if photos else None,
        note=None,
    )


def _iter_body(doc: DocxDocument):
    """Абзацы и таблицы в том порядке, в котором они идут в документе."""
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, doc)
        elif child.tag.endswith("}tbl"):
            yield Table(child, doc)


def parse_docx(source: bytes | str | Path, file_name: str) -> ParsedRegistry:
    """Разобрать «Вкусную тетрадь» из .docx вместе с фотографиями блюд."""
    handle: io.BytesIO | str = io.BytesIO(source) if isinstance(source, bytes) else str(source)
    try:
        doc = docx.Document(handle)
    except Exception as exc:  # noqa: BLE001 — python-docx кидает разное на битых файлах
        raise RegistryParseError(f"Не удалось прочитать Word-файл: {exc}") from exc

    builder = _RowBuilder()
    branch: str | None = None
    category: str | None = None

    for item in _iter_body(doc):
        if isinstance(item, Paragraph):
            text = " ".join(item.text.split())
            if not text:
                continue
            lowered = text.lower()
            if any(lowered.startswith(prefix) for prefix in _SKIP_PREFIXES):
                continue
            if any(marker in lowered for marker in _TITLE_MARKERS):
                continue
            if "кухня" in lowered:
                branch = text
                category = None
            else:
                category = text
            continue
        _parse_table(item, doc, builder, branch=branch, category=category)

    if not builder.rows:
        raise RegistryParseError(
            "В документе не нашлось ни одного блюда — проверьте, что меню оформлено таблицами"
        )

    # Картинки достаём из самого .docx: он zip, и открывается тем же путём,
    # что архив с медиа у Excel-залива.
    if isinstance(handle, io.BytesIO):
        handle.seek(0)
    archive = zipfile.ZipFile(handle)
    media_index: dict[str, str] = {}
    for info in archive.infolist():
        if info.is_dir() or not info.filename.startswith("word/media/"):
            continue
        media_index.setdefault(info.filename.lower(), info.filename)
        media_index.setdefault(PurePosixPath(info.filename).name.lower(), info.filename)

    return ParsedRegistry(
        rows=builder.rows,
        source_name=file_name,
        archive=archive,
        media_index=media_index,
    )

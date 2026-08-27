"""Разбор реестра «Вкусной тетради»: колонки, архив, кодировки имён.

Чистые юнит-тесты: ни БД, ни сети — только парсер.
"""
import io
import zipfile

import openpyxl
import pytest

from app.services.menu_import import (
    RegistryParseError,
    _media_keys,
    _member_names,
    parse_registry,
)

# Реальная шапка реестра — те же формулировки, что в файле заказчика.
HEADER = [
    "№",
    "Раздел",
    "Блюдо",
    "Ингредиенты (подписи)",
    "Текст озвучки",
    "Фото блюда (файл)",
    "Картинка ингредиентов (файл)",
    "Озвучка (файл)",
    "Картинка ингред. (Magnific)",
    "Озвучка (Magnific)",
]

ROW = [
    "1",
    "Холодные закуски",
    "Ассорти под крепкое",
    "Сельдь с луком, грибы, томаты",
    "Идеальный набор под крепкие напитки",
    "dish_photos/001_Ассорти.png",
    "images/001_Ассорти.png",
    "audio/001_Ассорти.mp3",
    "Открыть",
    "Открыть",
]


def build_xlsx(rows, header=None) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(header if header is not None else HEADER)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_parses_columns_by_header():
    registry = parse_registry(build_xlsx([ROW]), "реестр.xlsx")

    assert len(registry.rows) == 1
    row = registry.rows[0]
    assert row.name == "Ассорти под крепкое"
    assert row.category == "Холодные закуски"
    assert row.ingredients == "Сельдь с луком, грибы, томаты"
    assert row.description == "Идеальный набор под крепкие напитки"
    assert row.photo_dish == "dish_photos/001_Ассорти.png"
    assert row.photo_ingredients == "images/001_Ассорти.png"
    assert row.audio == "audio/001_Ассорти.mp3"


def test_ingredients_text_not_confused_with_ingredients_photo():
    """«Ингредиенты (подписи)» — текст, «Картинка ингредиентов (файл)» — путь.

    Обе колонки содержат слово «ингредиент», и спутать их — значит записать
    официанту в состав блюда имя файла.
    """
    registry = parse_registry(build_xlsx([ROW]), "реестр.xlsx")
    row = registry.rows[0]

    assert row.ingredients == "Сельдь с луком, грибы, томаты"
    assert row.photo_ingredients == "images/001_Ассорти.png"


def test_magnific_columns_are_ignored():
    """Колонки со ссылками на creations не должны попасть в озвучку."""
    registry = parse_registry(build_xlsx([ROW]), "реестр.xlsx")

    assert registry.rows[0].audio == "audio/001_Ассорти.mp3"


def test_columns_may_be_reordered():
    header = ["Блюдо", "Раздел", "Текст озвучки", "Ингредиенты (подписи)"]
    rows = [["Плов", "Горячее", "Рассказ про плов", "рис, баранина"]]

    registry = parse_registry(build_xlsx(rows, header=header), "реестр.xlsx")

    row = registry.rows[0]
    assert row.name == "Плов"
    assert row.category == "Горячее"
    assert row.description == "Рассказ про плов"
    assert row.ingredients == "рис, баранина"


def test_falls_back_to_column_order_when_header_unknown():
    header = ["a", "b", "c", "d", "e", "f", "g", "h"]
    rows = [["1", "Горячее", "Плов", "рис, баранина", "Рассказ", "p.png", "i.png", "a.mp3"]]

    registry = parse_registry(build_xlsx(rows, header=header), "реестр.xlsx")

    row = registry.rows[0]
    assert row.name == "Плов"
    assert row.category == "Горячее"
    assert row.audio == "a.mp3"


def test_dashes_and_blanks_read_as_empty():
    rows = [["1", "Горячее", "Плов", "—", "-", "", None, "–"]]

    registry = parse_registry(build_xlsx(rows), "реестр.xlsx")

    row = registry.rows[0]
    assert row.ingredients is None
    assert row.description is None
    assert row.audio is None


def test_rows_without_dish_name_are_skipped():
    rows = [ROW, ["2", "Холодные закуски", None, "", "", "", "", ""], ROW]

    registry = parse_registry(build_xlsx(rows), "реестр.xlsx")

    assert len(registry.rows) == 2


def test_registry_without_dishes_is_an_error():
    with pytest.raises(RegistryParseError, match="ни одного блюда"):
        parse_registry(build_xlsx([]), "реестр.xlsx")


def test_unsupported_extension_rejected():
    with pytest.raises(RegistryParseError, match="только .xlsx и .zip"):
        parse_registry(b"whatever", "меню.pdf")


def test_broken_zip_rejected():
    with pytest.raises(RegistryParseError, match="не zip"):
        parse_registry(b"not-an-archive", "меню.zip")


def test_zip_without_workbook_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("images/001.png", b"png-bytes")

    with pytest.raises(RegistryParseError, match="нет файла .xlsx"):
        parse_registry(buffer.getvalue(), "меню.zip")


def build_zip(extra_files=None, workbook_name="реестр.xlsx") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(workbook_name, build_xlsx([ROW]))
        for name, content in (extra_files or {}).items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_zip_media_resolved_by_path():
    data = build_zip(
        {
            "dish_photos/001_Ассорти.png": b"dish-photo",
            "images/001_Ассорти.png": b"ingredients-photo",
            "audio/001_Ассорти.mp3": b"voice",
        }
    )

    registry = parse_registry(data, "меню.zip")
    try:
        row = registry.rows[0]
        assert registry.read_media(row.photo_dish) == b"dish-photo"
        assert registry.read_media(row.photo_ingredients) == b"ingredients-photo"
        assert registry.read_media(row.audio) == b"voice"
    finally:
        registry.close()


def test_zip_media_resolved_by_basename_when_nested_deeper():
    """Заказчик пакует папку целиком — внутри архива путь на уровень глубже."""
    data = build_zip({"ЖУ/images/001_Ассорти.png": b"ingredients-photo"})

    registry = parse_registry(data, "меню.zip")
    try:
        assert registry.read_media(registry.rows[0].photo_ingredients) == b"ingredients-photo"
    finally:
        registry.close()


def test_missing_media_reads_as_none():
    registry = parse_registry(build_zip(), "меню.zip")
    try:
        assert registry.read_media(registry.rows[0].photo_dish) is None
    finally:
        registry.close()


def test_read_media_without_archive_is_none():
    registry = parse_registry(build_xlsx([ROW]), "реестр.xlsx")

    assert registry.read_media("images/001_Ассорти.png") is None


def test_temp_office_files_are_not_taken_for_the_registry():
    """~$-файл — временная копия Excel, реестром её считать нельзя."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("~$реестр.xlsx", b"garbage")
        archive.writestr("реестр.xlsx", build_xlsx([ROW]))

    registry = parse_registry(buffer.getvalue(), "меню.zip")
    try:
        assert registry.rows[0].name == "Ассорти под крепкое"
    finally:
        registry.close()


def test_member_names_recovers_cp866_filenames():
    """Архивы из проводника Windows пишут имена в CP866 без флага UTF-8.

    Без перекодировки zipfile отдаёт мусор из CP437, и пути из Excel никогда
    не совпадут с файлами в архиве.
    """
    original = "изображения/001_Ассорти.png"
    mojibake = original.encode("cp866").decode("cp437")
    info = zipfile.ZipInfo(mojibake)
    info.flag_bits = 0  # флага UTF-8 нет

    assert original in _member_names(info)


def test_member_names_keeps_utf8_name_as_is():
    info = zipfile.ZipInfo("images/001_Ассорти.png")
    info.flag_bits = 0x800

    assert _member_names(info) == ["images/001_Ассорти.png"]


def test_media_keys_cover_full_path_and_basename():
    assert _media_keys("Images/001_Ассорти.PNG") == [
        "images/001_ассорти.png",
        "001_ассорти.png",
    ]

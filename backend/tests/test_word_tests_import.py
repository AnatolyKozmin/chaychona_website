"""Тесты парсера Word для импорта тестов (нужен python-docx)."""

import io

import pytest

docx = pytest.importorskip("docx")


def test_parse_one_question_same_line_options() -> None:
    from docx import Document

    from app.word_tests_import import parse_docx_to_questions

    d = Document()
    p = d.add_paragraph()
    p.add_run("1. Сколько будет 2+2? ")
    p.add_run("A) 3")
    p.add_run(" B) ")
    r = p.add_run("4")
    r.bold = True
    p.add_run(" C) 5")

    buf = io.BytesIO()
    d.save(buf)
    questions, errors = parse_docx_to_questions(buf.getvalue())
    assert errors == []
    assert len(questions) == 1
    assert questions[0]["question_type"] == "single"
    assert questions[0]["text"] == "Сколько будет 2+2?"
    opts = questions[0]["options"]
    assert len(opts) == 3
    assert [o["text"] for o in opts] == ["3", "4", "5"]
    assert [o["is_correct"] for o in opts] == [False, True, False]


def test_parse_multiline_question() -> None:
    from docx import Document

    from app.word_tests_import import parse_docx_to_questions

    d = Document()
    d.add_paragraph("1. Первая строка вопроса")
    d.add_paragraph("вторая строка без номера")
    d.add_paragraph("A) нет")
    p = d.add_paragraph()
    p.add_run("B) ")
    r = p.add_run("да")
    r.bold = True

    buf = io.BytesIO()
    d.save(buf)
    questions, errors = parse_docx_to_questions(buf.getvalue())
    assert errors == []
    assert len(questions) == 1
    assert "Первая строка" in questions[0]["text"]
    assert "вторая строка" in questions[0]["text"]
    assert questions[0]["options"][1]["is_correct"] is True

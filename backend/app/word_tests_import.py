"""
Импорт вопросов теста из .docx.

Правила:
- Вопрос начинается с номера: «1.», «2.», …
- Текст вопроса — всё до первого варианта «A)» или «а)» (латинская A или кириллическая а).
- Варианты: строка начинается с «Буква)» (латиница или кириллица), в одной строке может быть несколько вариантов.
- Правильные ответы в Word выделены жирным (проверяется текст варианта после «X)»).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

QUESTION_START = re.compile(r"^(\d+)\.\s*(.*)$", re.DOTALL)
OPTION_IN_TEXT = re.compile(r"(?:^|[\s\u00a0])([A-Za-zА-Яа-я])\)\s*")


def find_first_option_index(text: str) -> int | None:
    """Индекс первого «A)» / «а)» / «a)» в строке (начало блока вариантов)."""
    m = OPTION_IN_TEXT.search(text)
    if m is None:
        return None
    return m.start()


def split_option_segments(tail: str) -> list[tuple[str, str, int, int]]:
    """
    tail — подстрока с первого варианта, например «A) один B) два».
    Возвращает (буква, текст, start, end) где start/end — границы текста варианта внутри tail.
    """
    matches = list(OPTION_IN_TEXT.finditer(tail))
    out: list[tuple[str, str, int, int]] = []
    for i, m in enumerate(matches):
        letter = m.group(1)
        c_start = m.end()
        c_end = matches[i + 1].start() if i + 1 < len(matches) else len(tail)
        content = tail[c_start:c_end].strip()
        out.append((letter, content, c_start, c_end))
    return out


def has_bold_in_range(para, abs_start: int, abs_end: int) -> bool:
    """Есть ли жирный фрагмент внутри [abs_start, abs_end) в параграфе."""
    pos = 0
    for run in para.runs:
        rlen = len(run.text)
        rstart = pos
        rend = pos + rlen
        if rend <= abs_start or rstart >= abs_end:
            pos = rend
            continue
        if run.bold and run.text.strip():
            return True
        pos = rend
    return False


def parse_options_from_tail(para, tail: str, tail_start_in_para: int) -> list[dict[str, str | bool]]:
    """Разбор нескольких вариантов в одной строке после первого «A)»."""
    options: list[dict[str, str | bool]] = []
    for letter, content, c_start, c_end in split_option_segments(tail):
        if not content:
            continue
        abs_start = tail_start_in_para + c_start
        abs_end = tail_start_in_para + c_end
        is_correct = has_bold_in_range(para, abs_start, abs_end)
        options.append({"text": content, "is_correct": is_correct, "letter": letter})
    return options


def parse_single_option_paragraph(para) -> dict[str, str | bool] | None:
    """Одна строка = один вариант «X) текст»."""
    raw = para.text
    leading = len(raw) - len(raw.lstrip())
    text = raw.strip()
    if not text:
        return None
    m = re.match(r"^\s*([A-Za-zА-Яа-я])\)\s*(.*)$", text, re.DOTALL)
    if not m:
        return None
    letter = m.group(1)
    body = m.group(2).strip()
    if not body:
        return None
    # жирность проверяем по диапазону текста ответа в исходной строке параграфа
    abs_start = leading + m.start(2)
    abs_end = leading + m.end(2)
    is_correct = has_bold_in_range(para, abs_start, abs_end)
    return {"text": body, "is_correct": is_correct, "letter": letter}


@dataclass
class ParsedQuestion:
    text: str
    options: list[dict[str, str | bool]]


def parse_question_group(group: list) -> ParsedQuestion | None:
    if not group:
        return None
    first = group[0]
    raw_first = first.text
    leading = len(raw_first) - len(raw_first.lstrip())
    full = raw_first.strip()
    if not full:
        return None
    qm = QUESTION_START.match(full)
    if not qm:
        return None
    rest = qm.group(2)
    idx = find_first_option_index(rest)

    options: list[dict[str, str | bool]] = []

    if idx is not None:
        q_text = rest[:idx].strip()
        tail = rest[idx:]
        # начало tail в координатах para.text
        tail_start_in_para = leading + qm.start(2) + idx
        options.extend(parse_options_from_tail(first, tail, tail_start_in_para))
        for para in group[1:]:
            opt = parse_single_option_paragraph(para)
            if opt:
                options.append(opt)
            else:
                q_text += "\n" + para.text.strip()
    else:
        q_parts = [rest.strip()]
        for para in group[1:]:
            opt = parse_single_option_paragraph(para)
            if opt:
                options.append(opt)
            else:
                q_parts.append(para.text.strip())
        q_text = "\n".join(p for p in q_parts if p)

    clean_opts: list[dict[str, str | bool]] = []
    for o in options:
        clean_opts.append({"text": str(o["text"]), "is_correct": bool(o["is_correct"])})

    if not q_text.strip():
        return None
    return ParsedQuestion(text=q_text.strip(), options=clean_opts)


def group_paragraphs_by_question(doc) -> list[list]:
    groups: list[list] = []
    current: list = []
    for para in doc.paragraphs:
        t = para.text.strip()
        if not t:
            continue
        if re.match(r"^\d+\.\s*", t):
            if current:
                groups.append(current)
            current = [para]
        else:
            if current:
                current.append(para)
    if current:
        groups.append(current)
    return groups


def parsed_to_quiz_questions(
    parsed: list[ParsedQuestion], strict: bool = True
) -> tuple[list[dict], list[str]]:
    """Преобразует в структуру для QuizTestCreate; собирает ошибки валидации.

    strict=True — проблемный вопрос отбрасывается, текст идёт в errors.
    strict=False — вопрос включается как есть, текст идёт в errors как предупреждение
    (правится вручную в предпросмотре на фронте).
    """
    from app.models.quiz import QuestionType

    out: list[dict] = []
    errors: list[str] = []
    for i, pq in enumerate(parsed, start=1):
        opts = pq.options
        if len(opts) < 2:
            errors.append(f"Вопрос {i}: нужно минимум 2 варианта ответа (найдено {len(opts)})")
            if strict:
                continue
        n_correct = sum(1 for o in opts if o["is_correct"])
        if n_correct < 1:
            errors.append(
                f"Вопрос {i}: отметьте жирным хотя бы один правильный ответ (или проверьте формат «A) текст»)"
            )
            if strict:
                continue
        if n_correct > 1:
            qtype = QuestionType.MULTIPLE.value
        else:
            qtype = QuestionType.SINGLE.value
        out.append(
            {
                "text": pq.text,
                "question_type": qtype,
                "options": [{"text": o["text"], "is_correct": o["is_correct"]} for o in opts],
            }
        )
    return out, errors


def parse_docx_to_questions(content: bytes, strict: bool = True) -> tuple[list[dict], list[str]]:
    """
    Читает .docx и возвращает (questions_payload, errors).

    strict=True: при любой ошибке уровня вопроса возвращается ([], errors) — импорт блокируется.
    strict=False (предпросмотр): возвращаются все разобранные вопросы, даже проблемные,
    а errors — предупреждения для показа пользователю; блокируют только фатальные
    ошибки (файл не читается / вопросов нет вовсе).
    """
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Установите пакет python-docx") from exc

    if not content:
        return [], ["Файл пустой"]

    try:
        doc = Document(io.BytesIO(content))
    except Exception as e:  # noqa: BLE001
        return [], [f"Не удалось прочитать Word: {e}"]

    groups = group_paragraphs_by_question(doc)
    if not groups:
        return [], ["В документе не найдено вопросов (строки должны начинаться с «1.», «2.», …)"]

    parsed: list[ParsedQuestion] = []
    block_errors: list[str] = []

    for gi, group in enumerate(groups, start=1):
        pq = parse_question_group(group)
        if pq is None:
            block_errors.append(f"Блок {gi}: не удалось разобрать вопрос (проверьте «1.» и варианты «A)»)")
            continue
        if strict and len(pq.options) < 2:
            block_errors.append(f"Блок {gi}: мало вариантов ответа (нужно минимум 2)")
            continue
        parsed.append(pq)

    questions, q_errors = parsed_to_quiz_questions(parsed, strict=strict)
    all_errors = block_errors + q_errors
    if strict and all_errors:
        return [], all_errors
    if not questions:
        return [], all_errors or ["Не удалось сформировать ни одного вопроса"]
    return questions, all_errors

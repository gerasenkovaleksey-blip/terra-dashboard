"""
Критерии определения лучшей школы потока.

Источник истины — таблица, которую заполняет руководитель кластера
(см. load_scorecard в data/loader.py). Названия критериев меняются от потока
к потоку, поэтому они читаются оттуда, а не хранятся в коде.

Статический список ниже — запасной вариант на случай, если таблица недоступна.
"""
from html import escape

# Резервный список — используется, только если таблица не прочиталась
FALLBACK_CRITERIA: list[str] = [
    "Собрана т. А",
    "Собрана т. Б",
    "Внедрена Минутка дарования",
    "Есть ли команда в школе",
    "Проведён благотворительный проект",
    "Есть ли деление на десятки",
    "Ежедневные / еженедельные отчёты у учеников",
    "Есть ли система бадди",
    "Доходимость до последнего занятия > 50%",
    "Разосланы приглашения на новый поток",
    "Нет скачков резкого удаления учеников более чем на 25% от недели к неделе",
    "Выпустила ли школа нового руководителя / куратора",
    "Регистрации на след. поток > 50%",
]


def _row(num: int, text: str, state: str | None) -> str:
    """
    Одна строка списка. state: 'yes', 'no' или None (галочек ещё нет).
    """
    if state == "yes":
        badge, bg, fg, color = "✓", "#22c55e", "#ffffff", "#0f172a"
    elif state == "no":
        badge, bg, fg, color = "—", "#fee2e2", "#ef4444", "#94a3b8"
    else:
        badge, bg, fg, color = str(num), "#e2e8f0", "#64748b", "#334155"
    return (
        '<div style="display:flex;gap:9px;align-items:flex-start;padding:6px 4px;'
        'break-inside:avoid">'
        f'<span style="flex-shrink:0;width:19px;height:19px;border-radius:50%;'
        f'background:{bg};color:{fg};font-size:0.62rem;font-weight:700;'
        'display:inline-flex;align-items:center;justify-content:center;'
        f'margin-top:1px">{badge}</span>'
        f'<span style="font-size:0.74rem;color:{color};line-height:1.45">'
        f"{escape(text)}</span></div>"
    )


def criteria_html(criteria: list[str] | None = None, marks: dict | None = None) -> str:
    """
    Список критериев в две колонки.

    criteria — названия из таблицы; None → резервный список.
    marks    — {критерий: bool} для конкретной школы. Если задан, вместо номеров
               показываются галочки. Если нет — просто пронумерованный список.
    """
    items = criteria or FALLBACK_CRITERIA
    body = ""
    for i, text in enumerate(items, start=1):
        state = None
        if marks is not None:
            state = "yes" if marks.get(text) else "no"
        body += _row(i, text, state)
    return f'<div style="columns:2;column-gap:26px">{body}</div>'


def scorecard_summary_html(done: int, total: int, score: float | None) -> str:
    """Строка-итог над списком: сколько пунктов закрыто и балл из таблицы."""
    pct = (done / total * 100) if total else 0
    color = "#22c55e" if pct >= 80 else "#f97316" if pct >= 50 else "#ef4444"
    score_html = (
        f'<div style="text-align:right"><div style="font-size:1.6rem;font-weight:800;'
        f'color:#1e293b;line-height:1">{score:.2f}</div>'
        '<div style="font-size:0.6rem;color:#94a3b8;text-transform:uppercase;'
        'letter-spacing:1px">итог по таблице</div></div>'
        if score is not None and score == score else ""
    )
    return (
        '<div style="display:flex;justify-content:space-between;align-items:center;'
        'gap:16px;margin-bottom:12px">'
        '<div style="flex:1;min-width:0">'
        f'<div style="font-size:0.78rem;font-weight:700;color:{color}">'
        f"Закрыто {done} из {total} пунктов</div>"
        '<div class="bar-track" style="margin-top:7px;height:8px">'
        f'<div class="bar-fill-{"green" if pct >= 80 else "orange" if pct >= 50 else "red"}" '
        f'style="width:{pct:.0f}%"></div></div></div>'
        f"{score_html}</div>"
    )

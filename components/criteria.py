"""
Критерии определения лучшей школы потока.

Список живёт в одном месте и выводится и на странице школы, и на сводной —
чтобы при изменении критериев не пришлось править их в двух файлах.
"""
from html import escape

BEST_SCHOOL_CRITERIA: list[str] = [
    "Собрана т. А",
    "Собрана т. Б",
    "Внедрена Минутка дарования",
    "Присутствует команда кураторов в школе",
    "Проведён благотворительный проект",
    "Ежедневные / еженедельные отчёты у учеников",
    "Внедрена система бадди",
    "Доходимость до последнего занятия &gt; 50%",
    "Разосланы приглашения на новый поток",
    "Выпустила ли школа нового руководителя / куратора",
    "Проведение открытого урока или иного мероприятия, направленного "
    "на привлечение новых людей в Терру",
    "Принесённый бюджет в фонд Терры через штрафы и благотворительные взносы",
    "Посещение руководителями или их заместителями общих совещаний по координации",
]

# Пункты, которые дашборд уже измеряет напрямую (нумерация с единицы).
# Подсвечиваем их, чтобы было видно, где цифры под рукой, а где нужна
# ручная оценка. Остальное дашборд подтвердить не может.
_TRACKED = {3, 8, 12}


def criteria_html(highlight_tracked: bool = True) -> str:
    """HTML со списком критериев в две колонки."""
    items = ""
    for i, text in enumerate(BEST_SCHOOL_CRITERIA, start=1):
        tracked = highlight_tracked and i in _TRACKED
        num_bg = "#2563eb" if tracked else "#e2e8f0"
        num_fg = "#ffffff" if tracked else "#64748b"
        mark = (
            '<span style="font-size:0.6rem;color:#2563eb;font-weight:700;'
            'white-space:nowrap"> · есть на дашборде</span>'
            if tracked else ""
        )
        items += (
            '<div style="display:flex;gap:9px;align-items:flex-start;'
            'padding:6px 4px;break-inside:avoid">'
            f'<span style="flex-shrink:0;width:19px;height:19px;border-radius:50%;'
            f'background:{num_bg};color:{num_fg};font-size:0.62rem;font-weight:700;'
            'display:inline-flex;align-items:center;justify-content:center;'
            f'margin-top:1px">{i}</span>'
            '<span style="font-size:0.74rem;color:#334155;line-height:1.45">'
            f'{text}{mark}</span>'
            "</div>"
        )

    return (
        '<div style="columns:2;column-gap:26px">' + items + "</div>"
        '<div style="margin-top:10px;font-size:0.65rem;color:#94a3b8;line-height:1.5">'
        "Синим отмечены пункты, по которым цифры уже есть на дашборде. "
        "Остальные оцениваются вручную."
        "</div>"
    )

import streamlit as st
import pandas as pd
from html import escape
import streamlit.components.v1 as components
from components.theme import inject_css, cluster_color
from components.auth import require_password
from components.bento import bento_header_html
from data.loader import (
    build_control_report, build_quality_report, load_registry, NPS_WINDOW_DAYS,
)


def registry_takes() -> int:
    """
    Активный поток по реестру — самое частое значение колонки «Поток берет?».
    Дешевле, чем сканировать таблицы школ, и реестр здесь и есть источник истины.
    """
    values = pd.to_numeric(load_registry()["Берёт поток"], errors="coerce").dropna()
    return int(values.mode().iloc[0]) if len(values) else 0

st.set_page_config(page_title="TERRA · Контроль", page_icon="🔒", layout="wide")
inject_css()

# ─── Пароль ──────────────────────────────────────────────────────────────────
# Ничего не грузим и не показываем, пока пароль не введён:
# так данные не утекут даже на мгновение.
if not require_password(
    "control_password",
    title="Контроль заполнения",
    hint="Раздел для управления. Пароль спрашивайте у администратора дашборда.",
):
    st.stop()

with st.sidebar:
    st.markdown("### ⭕ TERRA")
    if st.button("🔄 Обновить данные"):
        st.cache_data.clear()
        st.rerun()
    if st.button("🚪 Выйти"):
        st.session_state.pop("auth_ok_control_password", None)
        st.rerun()

# ─── Данные ──────────────────────────────────────────────────────────────────
with st.spinner("Сверяем данные всех школ..."):
    report = build_control_report()

lessons  = report["lessons"]
no_dates = report["no_dates"]
late     = report["late"]
lo, hi   = report["period"]

if lo is None or len(lessons) == 0 and len(no_dates) == 0:
    st.warning("Нет данных НПС для сверки")
    st.stop()

period_txt = f"{lo:%d.%m.%Y} — {hi:%d.%m.%Y}"

# ─── Метрики ─────────────────────────────────────────────────────────────────
st_counts = lessons["Статус"].value_counts() if len(lessons) else pd.Series(dtype=int)
n_ok      = int(st_counts.get("Совпало", 0))
n_under   = int(st_counts.get("Не заполнили", 0))
n_over    = int(st_counts.get("Кураторы / открытый", 0))
n_date    = int(st_counts.get("Проверить дату", 0))
n_empty   = int(st_counts.get("Форм нет", 0))
n_written = n_ok + n_under + n_over + n_date          # занятия с заполненными формами
accuracy  = round(n_ok / n_written * 100, 1) if n_written else None
late_total = int(late["Ответов"].sum()) if len(late) else 0

kpis = [
    {"label": "Занятий сверено", "num": len(lessons),  "icon": "📋", "color": "#64748b"},
    {"label": "Совпало",         "num": n_ok,          "icon": "✅", "color": "#22c55e"},
    {"label": "Не заполнили",    "num": n_under,       "icon": "📉", "color": "#ef4444"},
    {"label": "Проверить дату",  "num": n_date,        "icon": "📌", "color": "#f97316"},
    {"label": "Кураторы / откр.","num": n_over,        "icon": "➕", "color": "#2563eb"},
    {"label": "Форм нет вовсе",  "num": n_empty,       "icon": "⬜", "color": "#94a3b8"},
    {"label": "Школ без дат",    "num": len(no_dates), "icon": "📅", "color": "#f97316"},
    {"label": "Ответов мимо",    "num": late_total,    "icon": "🕓", "color": "#8b5cf6", "sep": True},
]

# Кольцо в шапке использует шкалу 0–10, поэтому проценты приводим к ней
components.html(
    bento_header_html(
        title="Контроль заполнения",
        subtitle=f"Период НПС: {period_txt}",
        kpis=kpis,
        avg_rating=(accuracy / 10) if accuracy is not None else None,
        rating_label="Точность заполнения",
        rating_note=(f"совпало {n_ok} из {n_written} занятий "
                     f"с заполненными формами" if n_written else "нет данных"),
        schools_note=f"{len(no_dates) + lessons['Школа'].nunique()} школ в сверке",
        trend_note=f"Форма засчитывается в день занятия или +{NPS_WINDOW_DAYS} дн.",
        accent="#0284c7",
        pill={"text": "только для управления", "color": "#0284c7"},
    ),
    height=290,
    scrolling=True,
)

st.caption(
    "В таблицы школ ничего не записывается — страница только сверяет "
    "записанное количество форм с фактическим числом ответов НПС."
)

# ─── Текущий поток ───────────────────────────────────────────────────────────
# Берём из реестра (колонка «Поток берет?») — это дешевле, чем сканировать
# таблицы школ, и именно реестр говорит, какой поток сейчас активен.
_takes = registry_takes()
current_stream = _takes if _takes else 0

tab_lessons, tab_quality = st.tabs(["📋 Сверка занятий", "🧪 Качество данных"])

# ─── Вкладка 1: сверка занятий ───────────────────────────────────────────────
with tab_lessons:
    # ─── Сверка по занятиям ──────────────────────────────────────────────────────
    _STATUS_COLOR = {
        "Не заполнили":        "#ef4444",
        "Проверить дату":      "#f97316",
        "Кураторы / открытый": "#2563eb",
        "Совпало":             "#22c55e",
        "Форм нет":            "#94a3b8",
    }

    with st.container(border=True):
        st.markdown('<div class="sec-title">🔍 Сверка по занятиям</div>', unsafe_allow_html=True)

        if len(lessons) == 0:
            st.info("Нет занятий с датами в периоде НПС")
        else:
            order = ["Все", "Не заполнили", "Проверить дату", "Кураторы / открытый",
                     "Форм нет", "Совпало"]
            choice = st.radio("Фильтр", order, horizontal=True, label_visibility="collapsed")

            view = lessons if choice == "Все" else lessons[lessons["Статус"] == choice]
            # Сначала самые крупные недоборы — с ними и надо разбираться в первую очередь
            view = view.sort_values(
                ["Разница", "Факт"], ascending=[True, False], na_position="last"
            )

            if len(view) == 0:
                st.success(f"Нет занятий в категории «{choice}»")
            else:
                _TH = ("position:sticky;top:0;background:#f8fafc;padding:9px 11px;text-align:left;"
                       "font-size:12px;color:#1e293b;font-weight:700;"
                       "border-bottom:2px solid #e2e8f0;white-space:nowrap;z-index:2")
                _TD = ("padding:7px 11px;font-size:12px;border-bottom:1px solid #f1f5f9;"
                       "white-space:nowrap;color:#334155")

                head = "".join(f'<th style="{_TH}">{h}</th>' for h in
                               ["Школа", "Кластер", "Зан.", "Дата", "Учеников",
                                "Записано", "Факт НПС", "Разница", "Статус"])
                body = ""
                for _, r in view.iterrows():
                    cl = str(r["Кластер"]) if pd.notna(r["Кластер"]) else ""
                    cc = cluster_color(cl)
                    sc = _STATUS_COLOR.get(r["Статус"], "#64748b")
                    diff = r["Разница"]
                    if pd.isna(diff):
                        diff_html = "—"
                    else:
                        diff = int(diff)
                        dc = "#ef4444" if diff < 0 else "#2563eb" if diff > 0 else "#22c55e"
                        diff_html = (f'<span style="color:{dc};font-weight:700">'
                                     f'{diff:+d}</span>')
                    body += (
                        f'<tr>'
                        f'<td style="{_TD};font-weight:600;color:#0f172a">{escape(str(r["Школа"]))}</td>'
                        f'<td style="{_TD}"><span class="pill" style="background:{cc}18;color:{cc}">'
                        f'{escape(cl)}</span></td>'
                        f'<td style="{_TD}">{"" if pd.isna(r["Занятие"]) else int(r["Занятие"])}</td>'
                        f'<td style="{_TD}">{r["Дата"]:%d.%m}</td>'
                        f'<td style="{_TD}">{"—" if pd.isna(r["Учеников"]) else int(r["Учеников"])}</td>'
                        f'<td style="{_TD}">{"—" if r["Записано"] is None or pd.isna(r["Записано"]) else int(r["Записано"])}</td>'
                        f'<td style="{_TD};font-weight:700">{int(r["Факт"])}</td>'
                        f'<td style="{_TD}">{diff_html}</td>'
                        f'<td style="{_TD}"><span class="pill" style="background:{sc}18;color:{sc}">'
                        f'{escape(str(r["Статус"]))}</span></td>'
                        f'</tr>'
                    )

                html = (
                    '<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
                    'body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}'
                    'table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}'
                    'tbody tr{transition:background .2s,box-shadow .2s}'
                    'tbody tr:hover{background:#f0f9ff;box-shadow:inset 3px 0 0 #0284c7}'
                    '.pill{display:inline-block;padding:2px 9px;border-radius:20px;'
                    'font-size:11px;font-weight:700;white-space:nowrap}'
                    '</style></head><body><table>'
                    f'<thead><tr>{head}</tr></thead><tbody>{body}</tbody>'
                    '</table></body></html>'
                )
                components.html(html, height=min(430, 46 + len(view) * 33), scrolling=True)
                st.caption(f"Показано {len(view)} из {len(lessons)} занятий")

    # ─── Школы без дат и непривязанные ответы ────────────────────────────────────
    col_l, col_r = st.columns(2)

    with col_l:
        with st.container(border=True):
            st.markdown('<div class="sec-title">📅 Даты занятий не проставлены</div>',
                        unsafe_allow_html=True)
            if len(no_dates) == 0:
                st.success("Все школы с активным НПС ведут расписание")
            else:
                rows = ""
                for _, r in no_dates.sort_values("Ответов", ascending=False).iterrows():
                    color = "#ef4444" if r["Ответов"] >= 40 else "#f97316" if r["Ответов"] >= 10 else "#94a3b8"
                    rows += (
                        f'<div class="bar-row" style="display:flex;align-items:baseline;gap:10px;'
                        f'margin-bottom:6px">'
                        f'<span style="flex:1;min-width:0;font-size:0.72rem;font-weight:600;color:#0f172a;'
                        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
                        f'{escape(str(r["Школа"]))}</span>'
                        f'<span style="font-size:0.64rem;color:#94a3b8;flex-shrink:0">'
                        f'{escape(str(r["Дни по НПС"]))}</span>'
                        f'<span style="font-size:0.75rem;font-weight:800;color:{color};'
                        f'flex-shrink:0;min-width:32px;text-align:right">{int(r["Ответов"])}</span>'
                        f'</div>'
                    )
                st.markdown(rows, unsafe_allow_html=True)
                st.caption("Занятия идут — это видно по кучности НПС, — но расписание не заполнено")

    with col_r:
        with st.container(border=True):
            st.markdown('<div class="sec-title">🕓 Ответы вне окна занятия</div>',
                        unsafe_allow_html=True)
            if len(late) == 0:
                st.success("Все ответы попали в окно занятий")
            else:
                rows = ""
                for _, r in late.sort_values("Ответов", ascending=False).iterrows():
                    hint = r["Похоже на занятие"]
                    note = (f'скопление {escape(str(hint))} — похоже на занятие вне таблицы'
                            if hint else "одиночные — опоздавшие")
                    color = "#ef4444" if hint else "#94a3b8"
                    rows += (
                        f'<div class="bar-row" style="display:flex;align-items:baseline;gap:10px;'
                        f'margin-bottom:6px">'
                        f'<span style="flex:1;min-width:0;font-size:0.72rem;font-weight:600;color:#0f172a;'
                        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
                        f'{escape(str(r["Школа"]))}</span>'
                        f'<span style="font-size:0.64rem;color:#94a3b8;flex-shrink:0">{note}</span>'
                        f'<span style="font-size:0.75rem;font-weight:800;color:{color};'
                        f'flex-shrink:0;min-width:32px;text-align:right">{int(r["Ответов"])}</span>'
                        f'</div>'
                    )
                st.markdown(rows, unsafe_allow_html=True)
                st.caption("Крупные скопления в один день — это, скорее всего, занятия, "
                           "которых нет в таблице")

# ─── Вкладка 2: качество данных ──────────────────────────────────────────────
with tab_quality:
    with st.spinner("Проверяем таблицы школ..."):
        q = build_quality_report(current_stream)

    _CHECKS = [
        ("pct_bad",    "⚖️", "Процент ≠ количествам",   "#ef4444"),
        ("forms_over", "📈", "Форм больше учеников",     "#2563eb"),
        ("half",       "◧",  "Заполнено одно из двух",   "#f97316"),
        ("date_bad",   "📅", "Проблемы с датами",        "#f97316"),
        ("no_rows",    "🚫", "Берут поток, данных нет",  "#ef4444"),
        ("broken",     "🔗", "Битые ссылки в реестре",   "#94a3b8"),
        ("ghosts",     "🔤", "Имена школ не совпали",    "#22c55e"),
    ]
    total = sum(len(q[k]) for k, *_ in _CHECKS)

    st.markdown(
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'gap:14px;margin-bottom:10px">'
        f'<div><div style="font-size:1.05rem;font-weight:700;color:#1e293b">'
        f'Где таблица противоречит сама себе</div>'
        f'<div style="font-size:0.7rem;color:#64748b;margin-top:3px">'
        f'Ничего не исправляем — показываем, чтобы школа поправила у себя</div></div>'
        f'<div style="text-align:right"><div style="font-size:1.9rem;font-weight:800;'
        f'color:{"#22c55e" if total == 0 else "#8b5cf6"};line-height:1">{total}</div>'
        f'<div style="font-size:0.6rem;color:#94a3b8;text-transform:uppercase;'
        f'letter-spacing:1px">находок</div></div></div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(len(_CHECKS))
    for col, (key, icon, label, color) in zip(cols, _CHECKS):
        n = len(q[key])
        with col:
            st.markdown(
                f'<div class="kpi-card" style="--accent:{color if n else "#22c55e"}">'
                f'<div style="font-size:1rem;margin-bottom:6px">{icon}</div>'
                f'<div class="kpi-value" style="font-size:1.5rem;'
                f'color:{color if n else "#22c55e"}">{n}</div>'
                f'<div class="kpi-label">{escape(label)}</div></div>',
                unsafe_allow_html=True,
            )

    if total == 0:
        st.success("Все проверки пройдены — таблицы школ согласованы")

    def _section(key: str, title: str, hint: str, columns: list[str]) -> None:
        """Карточка с находками одной проверки. Пустые проверки не показываем."""
        df = q[key]
        if len(df) == 0:
            return
        with st.container(border=True):
            st.markdown(f'<div class="sec-title">{title} · {len(df)}</div>',
                        unsafe_allow_html=True)
            show = [c for c in columns if c in df.columns]
            st.dataframe(df[show], use_container_width=True, hide_index=True)
            st.caption(hint)

    _section(
        "pct_bad", "⚖️ Процент в таблице не сходится с количествами",
        "Дашборд считает по количествам — колонка «По факту». Строки здесь, "
        "чтобы школа поправила процент у себя в таблице.",
        ["Школа", "Поток", "Занятие", "Учеников", "Форм", "В таблице", "По факту", "Дельта"],
    )
    _section(
        "forms_over", "📈 Форм сдано больше, чем было учеников",
        "Это нормально: кураторы тоже заполняют форму, плюс открытые уроки. "
        "Строки видны, потому что раньше именно они ломали расчёт процента.",
        ["Школа", "Поток", "Занятие", "Учеников", "Форм", "Процент"],
    )
    _section(
        "half", "◧ Заполнено только одно поле из двух",
        "Есть количество учеников, но нет форм — или наоборот. Процент по такой "
        "строке посчитать нельзя, занятие выпадает из статистики.",
        ["Школа", "Поток", "Занятие", "Дата", "Чего нет"],
    )
    _section(
        "date_bad", f"📅 Проблемы с датами занятий (поток {current_stream})",
        "Занятия еженедельные, поэтому разрыв не в 7 дней и задвоенные даты — "
        "повод проверить. Из-за сдвига даты ответы НПС не привязываются к занятию.",
        ["Школа", "Задвоено", "Разрывы"],
    )
    _section(
        "no_rows", f"🚫 В реестре стоит «поток {current_stream}», но строк потока нет",
        "Именно поэтому в реестре школ больше, чем видно на сводной странице.",
        ["Школа", "Кластер", "Строк потока"],
    )
    _section(
        "broken", "🔗 Таблицу школы не удалось прочитать",
        "Ссылка в реестре не работает или таблица закрыта. Данные этих школ "
        "не попадают на дашборд вообще.",
        ["Школа", "Причина"],
    )
    _section(
        "ghosts", "🔤 Название школы в форме НПС не совпадает с реестром",
        "Расхождение хоть на один пробел — и все оценки этой школы молча "
        "выпадают из дашборда. Название в форме нужно привести к реестру.",
        ["Название в форме", "Ответов"],
    )

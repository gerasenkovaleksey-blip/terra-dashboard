import streamlit as st
import pandas as pd
from html import escape
import streamlit.components.v1 as components
from components.theme import (
    inject_css, bar_row, cluster_color, rating_color, rating_verdict,
)
from components.bento import bento_header_html
from components.criteria import criteria_html, scorecard_summary_html
from data.loader import (
    load_registry, load_minutka, load_fines, school_metrics,
    load_school_ratings, get_school_rating, load_scorecard,
)

st.set_page_config(page_title="TERRA · Школа", page_icon="🏫", layout="wide")
inject_css()

# ─── Sidebar ─────────────────────────────────────────────────────────────────
registry = load_registry()
school_names = registry["Школа"].tolist()

with st.sidebar:
    st.markdown("### ⭕ TERRA")
    selected_school = st.selectbox("Школа", school_names)

school_row = registry[registry["Школа"] == selected_school].iloc[0]
sheet_id   = school_row["sheet_id"]
cluster    = school_row["Кластер"] if pd.notna(school_row["Кластер"]) else "—"
accent      = cluster_color(cluster)
leader_name = str(school_row.get("Руководитель") or "").strip()
leader_tg   = str(school_row.get("Телеграм") or "").strip()

if not sheet_id:
    st.warning(f"Для школы «{selected_school}» не указана ссылка на таблицу.")
    st.stop()

try:
    minutka_df = load_minutka(sheet_id)
    fines_df   = load_fines(sheet_id)
except Exception as e:
    err_str = str(e)
    if "403" in err_str:
        reason = "таблица не открыта для публичного доступа (403 Forbidden)"
    elif "404" in err_str:
        reason = "таблица не найдена — возможно, ссылка устарела (404 Not Found)"
    else:
        reason = err_str
    st.error(
        f"**Не удалось загрузить данные школы «{selected_school}»**\n\n"
        f"Причина: {reason}\n\n"
        f"`sheet_id: {sheet_id}`"
    )
    st.stop()

streams = sorted(
    minutka_df["Поток"].dropna().astype(int).unique().tolist(), reverse=True
)

with st.sidebar:
    if not streams:
        st.warning("Нет данных по потокам")
        st.stop()
    selected_stream = st.selectbox("Поток", streams)
    if st.button("🔄 Обновить данные"):
        st.cache_data.clear()
        st.rerun()

metrics = school_metrics(minutka_df, fines_df, selected_stream)
ml = metrics["minutka_by_lesson"]

# ─── Рейтинг школы (нужен и в шапке, и в разделе внизу) ──────────────────────
ratings = load_school_ratings()
rating = get_school_rating(ratings, selected_school)

# ─── История потоков для спарклайнов ─────────────────────────────────────────
# Данные школы уже загружены целиком, поэтому метрики по прошлым потокам
# считаются локально — ни одного лишнего запроса в сеть.
HISTORY_DEPTH = 6
hist_streams = tuple(sorted(s for s in streams if s <= selected_stream))[-HISTORY_DEPTH:]
hist = {s: school_metrics(minutka_df, fines_df, s) for s in hist_streams}


def _trend(key: str) -> list[float]:
    """Значения метрики по потокам hist_streams — данные для спарклайна."""
    if len(hist_streams) < 2:
        return []
    return [float(hist[s][key]) for s in hist_streams]


kpis = [
    {"label": "Пришли на 1-е занятие", "num": metrics["first_lesson_students"],
     "icon": "👥", "color": "#2563eb", "sep": True, "series": _trend("first_lesson_students")},
    {"label": "Дошли до последнего",   "num": metrics["last_lesson_students"],
     "icon": "🎓", "color": "#2563eb", "sep": True, "series": _trend("last_lesson_students")},
    {"label": "% отсева",              "num": metrics["dropout_pct"],
     "icon": "📉", "color": "#ef4444", "dec": 1, "suf": "%", "series": _trend("dropout_pct")},
    {"label": "Штрафов назначено",     "num": int(metrics["total_fines"]),
     "icon": "📋", "color": "#ef4444", "sep": True, "suf": "₽", "series": _trend("total_fines")},
    {"label": "Штрафы оплачены",       "num": int(metrics["total_fines_paid"]),
     "icon": "⚠️", "color": "#f97316", "sep": True, "suf": "₽", "series": _trend("total_fines_paid")},
    {"label": "Минутка дарования",     "num": metrics["avg_minutka_pct"],
     "icon": "✨", "color": "#22c55e", "dec": 1, "suf": "%", "series": _trend("avg_minutka_pct")},
]

trend_note = (
    f"Тренд на спарклайнах: потоки {hist_streams[0]}–{hist_streams[-1]}"
    if len(hist_streams) >= 2 else
    "Тренд появится со второго потока школы"
)

components.html(
    bento_header_html(
        title=selected_school,
        subtitle=f"Поток {selected_stream}",
        kpis=kpis,
        avg_rating=rating["score"] if rating else None,
        rating_label="Рейтинг школы",
        rating_note=(f"На основе {rating['count']} оценок" if rating else ""),
        schools_note=f"{len(ml)} занятий · поток {selected_stream}",
        trend_note=trend_note,
        accent=accent,
        pill={"text": str(cluster), "color": accent} if cluster != "—" else None,
        leader={"name": leader_name, "url": leader_tg} if leader_name else None,
        rating_color=rating_color(rating["score"]) if rating else None,
        rating_verdict=rating_verdict(rating["score"]) if rating else None,
    ),
    height=290,
    # У iframe высота фиксированная: на узком экране KPI переносятся на второй
    # ряд и не помещаются. scrolling оставляет их доступными, а не обрезает —
    # на десктопе контент влезает целиком, поэтому полосы прокрутки не будет.
    scrolling=True,
)

# ─── Воронка отсева ──────────────────────────────────────────────────────────
first = metrics["first_lesson_students"]
last  = metrics["last_lesson_students"]
dropout_pct = metrics["dropout_pct"]

with st.container(border=True):
    st.markdown('<div class="sec-title">📉 Воронка отсева</div>', unsafe_allow_html=True)
    if first > 0:
        dropped = first - last
        remaining_pct = max(0, min(100, 100 - dropout_pct))
        st.markdown(f"""
<div style="display:flex;align-items:center;gap:24px;padding:8px 0">
  <div style="text-align:center;flex:1">
    <div style="font-size:2.5rem;font-weight:800;color:#2563eb">{first}</div>
    <div style="font-size:0.65rem;color:#94a3b8;text-transform:uppercase;letter-spacing:1px">Старт</div>
  </div>
  <div style="font-size:1.5rem;color:#cbd5e1">→</div>
  <div style="text-align:center;flex:2">
    <div style="font-size:0.75rem;color:#ef4444;font-weight:700">−{dropped} чел. ({max(0, dropout_pct):.1f}%)</div>
    <div class="bar-track" style="margin:8px 0;height:6px">
      <div class="bar-fill-blue" style="width:{remaining_pct:.0f}%"></div>
    </div>
    <div style="font-size:0.65rem;color:#94a3b8">Осталось {remaining_pct:.0f}%</div>
  </div>
  <div style="font-size:1.5rem;color:#cbd5e1">→</div>
  <div style="text-align:center;flex:1">
    <div style="font-size:2.5rem;font-weight:800;color:#22c55e">{last}</div>
    <div style="font-size:0.65rem;color:#94a3b8;text-transform:uppercase;letter-spacing:1px">Финиш</div>
  </div>
</div>
""", unsafe_allow_html=True)
    else:
        st.info("Нет данных по посещаемости за этот поток")

# ─── Посещаемость и штрафы ───────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    with st.container(border=True):
        st.markdown('<div class="sec-title">📊 Посещаемость по занятиям</div>',
                    unsafe_allow_html=True)
        if len(ml) > 0:
            max_students = int(ml["Количество учеников в школе"].max())
            bars_html = ""
            for _, row in ml.iterrows():
                n = int(row["Количество учеников в школе"]) if pd.notna(row["Количество учеников в школе"]) else 0
                bars_html += bar_row(f"Занятие {int(row['Занятие'])}", n, max_students or 1, str(n), "blue")
            st.markdown(bars_html, unsafe_allow_html=True)
        else:
            st.info("Нет данных за выбранный поток")

with col_right:
    with st.container(border=True):
        st.markdown('<div class="sec-title">⚠️ Штрафы по причинам</div>',
                    unsafe_allow_html=True)
        fbr = metrics["fines_by_reason"]
        if len(fbr) > 0:
            total_f = fbr.sum()
            bars_html = ""
            for reason, amount in fbr.items():
                if amount > 0:
                    bars_html += bar_row(reason, amount, total_f or 1,
                                         f"{int(amount):,}₽".replace(",", " "), "orange")
            st.markdown(bars_html, unsafe_allow_html=True)
            st.markdown(
                f"<div style='margin-top:12px;font-size:0.7rem;color:#64748b'>Итого: "
                f"<b style='color:#f97316'>{int(total_f):,}₽</b></div>".replace(",", " "),
                unsafe_allow_html=True
            )
        else:
            st.success("Штрафов нет")

# ─── Минутка дарования ───────────────────────────────────────────────────────
avg_pct = metrics["avg_minutka_pct"]
ring_pct = min(100, max(0, avg_pct))
ring_color = "#22c55e" if ring_pct >= 80 else "#f97316" if ring_pct >= 50 else "#ef4444"

with st.container(border=True):
    st.markdown('<div class="sec-title">✨ Минутка дарования</div>', unsafe_allow_html=True)
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:24px;margin-bottom:16px">
  <div class="gauge" style="width:80px;height:80px;background:conic-gradient({ring_color} 0% {ring_pct:.0f}%, #e2e8f0 {ring_pct:.0f}% 100%)">
    <div class="gauge-hole"><span style="font-size:0.85rem;color:{ring_color}">{avg_pct:.0f}%</span></div>
  </div>
  <div>
    <div style="font-size:1rem;font-weight:700;color:{ring_color}">{avg_pct:.1f}%</div>
    <div style="font-size:0.65rem;color:#94a3b8;text-transform:uppercase;letter-spacing:1px">Средний % за поток</div>
  </div>
</div>
""", unsafe_allow_html=True)

    st.markdown("**По занятиям:**")
    if len(ml) > 0:
        bars_html = ""
        for _, row in ml.iterrows():
            pct = float(row["Процент выполнения"]) if pd.notna(row["Процент выполнения"]) else 0.0
            bars_html += bar_row(f"Занятие {int(row['Занятие'])}", pct, 100, f"{pct:.1f}%", "green")
        st.markdown(bars_html, unsafe_allow_html=True)
    else:
        st.info("Нет данных")

# ─── Рейтинг школы (NPS) ──────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown('<div class="sec-title">⭐ Рейтинг школы</div>', unsafe_allow_html=True)

    if rating:
        score = rating["score"]
        count = rating["count"]
        gauge_pct = min(100, max(0, score / 10 * 100))
        gauge_color = rating_color(score)
        verdict = rating_verdict(score)
        st.markdown(f"""
<div style="display:flex;align-items:center;gap:28px;padding:8px 0">
  <div class="gauge" style="width:140px;height:140px;background:conic-gradient({gauge_color} 0% {gauge_pct:.1f}%, #e2e8f0 {gauge_pct:.1f}% 100%)">
    <div class="gauge-hole" style="inset:12px">
      <span style="font-size:1.9rem;color:{gauge_color}">{score:.2f}</span>
    </div>
  </div>
  <div>
    <div style="font-size:1.05rem;font-weight:700;color:{gauge_color}">{verdict}</div>
    <div style="font-size:0.7rem;color:#94a3b8;margin-top:4px">
        Средняя оценка удовлетворённости учеников
    </div>
    <div style="font-size:0.7rem;color:#64748b;margin-top:10px">
        На основе <b>{count}</b> оценок
    </div>

  </div>
</div>
""", unsafe_allow_html=True)
    else:
        st.info("Пока нет отзывов по этой школе")

# ─── Критерии лучшей школы потока ────────────────────────────────────────────
with st.container(border=True):
    st.markdown('<div class="sec-title">🏆 Критерии лучшей школы потока</div>',
                unsafe_allow_html=True)
    try:
        card = load_scorecard()
    except Exception as e:
        card = {"data": pd.DataFrame(), "criteria": [], "filled": False}
        st.caption(f"Чек-лист недоступен: {e}")

    crit = card["criteria"] or None
    row = None
    if len(card["data"]):
        hit = card["data"][card["data"]["Школа"] == selected_school]
        if len(hit):
            row = hit.iloc[0]

    if row is not None and card["filled"]:
        marks = {c: bool(row[c]) for c in card["criteria"]}
        st.markdown(
            scorecard_summary_html(int(row["Отмечено"]), len(card["criteria"]),
                                   row.get("Итог")),
            unsafe_allow_html=True,
        )
        st.markdown(criteria_html(crit, marks), unsafe_allow_html=True)
    else:
        st.markdown(criteria_html(crit), unsafe_allow_html=True)
        st.caption(
            "Галочки проставляет руководитель кластера в отдельной таблице. "
            "По этому потоку она ещё не заполнена — появится здесь автоматически."
        )

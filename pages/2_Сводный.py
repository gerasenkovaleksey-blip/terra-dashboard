import streamlit as st
import pandas as pd
from html import escape
import streamlit.components.v1 as components
from components.theme import (
    inject_css, bar_row, cluster_color, DEFAULT_ACCENT,
    rating_color, rating_verdict, rating_bar_class, RATING_EXCELLENT,
)
from components.bento import bento_header_html
from components.criteria import criteria_html, scorecard_summary_html
from data.loader import (
    load_registry, load_minutka, load_all_schools_summary, load_all_fines_detail,
    load_school_ratings, load_streams_history, load_scorecard,
)

st.set_page_config(page_title="TERRA · Сводный", page_icon="📊", layout="wide")
inject_css()

# ─── Sidebar ─────────────────────────────────────────────────────────────────
registry = load_registry()

@st.cache_data(ttl=3600)
def _get_all_streams() -> list[int]:
    """Объединяем потоки из всех школ реестра."""
    all_streams: set[int] = set()
    for _, row in registry.iterrows():
        sid = row["sheet_id"]
        if not sid:
            continue
        try:
            m = load_minutka(sid)
            all_streams.update(m["Поток"].dropna().astype(int).unique().tolist())
        except Exception:
            continue
    return sorted(all_streams, reverse=True)

with st.sidebar:
    st.markdown("### ⭕ TERRA")
    streams = _get_all_streams()
    if not streams:
        st.warning("Нет данных по потокам")
        st.stop()
    selected_stream = st.selectbox("Поток", streams)

    clusters = ["Все кластеры"] + sorted(registry["Кластер"].dropna().unique().tolist())
    selected_cluster = st.selectbox("Кластер", clusters)

    school_names_list = ["Все школы"] + sorted(registry["Школа"].dropna().unique().tolist())
    selected_school_filter = st.selectbox("Школа", school_names_list)

    if st.button("🔄 Обновить данные"):
        st.cache_data.clear()
        st.rerun()

# ─── Загрузка сводных данных ─────────────────────────────────────────────────
with st.spinner("Загрузка данных всех школ..."):
    summary = load_all_schools_summary(selected_stream)

if selected_cluster != "Все кластеры":
    summary = summary[summary["Кластер"] == selected_cluster]
if selected_school_filter != "Все школы":
    summary = summary[summary["Школа"] == selected_school_filter]

# Рейтинг школ (0-10) — общий по всем потокам, не привязан к выбранному потоку
ratings = load_school_ratings()
summary = summary.merge(ratings[["Школа", "Рейтинг", "Отзывов"]], on="Школа", how="left")

cluster_label = selected_cluster if selected_cluster != "Все кластеры" else "Все кластеры"

if len(summary) == 0:
    st.markdown(f"""
    <div class="terra-header">
      <div class="terra-ring"></div>
      <div>
        <div style="font-size:1.2rem;font-weight:700;color:#1e293b">Сводный дашборд</div>
        <div style="font-size:0.65rem;color:#2563eb;letter-spacing:2px;text-transform:uppercase">
            {escape(cluster_label)} · Поток {selected_stream}
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.warning("Нет данных за выбранный поток / кластер")
    st.stop()

# ─── KPI ─────────────────────────────────────────────────────────────────────
total_start  = int(summary["Старт"].sum())
total_finish = int(summary["Финиш"].sum())
avg_dropout  = round(summary["Отсев %"].mean(), 1)
total_fines          = int(summary["Штрафы ₽"].sum())
total_fines_assigned = int(summary["Штрафов назначено ₽"].sum())
avg_rating = round(summary["Рейтинг"].mean(), 2) if summary["Рейтинг"].notna().any() else None

# ─── История потоков для спарклайнов ─────────────────────────────────────────
# Берём до 6 последних потоков включительно. XLSX школ уже лежат в кэше после
# load_all_schools_summary(), поэтому сети тут нет — только пересчёт метрик.
HISTORY_DEPTH = 6
hist_streams = tuple(s for s in sorted(streams) if s <= selected_stream)[-HISTORY_DEPTH:]
history = load_streams_history(hist_streams)

# Те же фильтры, что и для summary — тренд должен соответствовать тому, что на экране
if len(history) > 0:
    if selected_cluster != "Все кластеры":
        history = history[history["Кластер"] == selected_cluster]
    if selected_school_filter != "Все школы":
        history = history[history["Школа"] == selected_school_filter]


def _trend(col: str, how: str = "sum") -> list[float]:
    """
    Ряд значений метрики по потокам hist_streams — данные для спарклайна.
    Потоки, где школы ещё не было, дают 0: новая школа стартует с нуля.
    """
    if len(hist_streams) < 2 or len(history) == 0:
        return []
    if how == "count":
        series = history.groupby("Поток").size()
    elif how == "mean":
        series = history.groupby("Поток")[col].mean()
    else:
        series = history.groupby("Поток")[col].sum()
    return [float(series.get(s, 0.0)) for s in hist_streams]


kpis = [
    {"label": "Школ в потоке",      "num": len(summary),         "icon": "🏫", "color": "#2563eb",
     "series": _trend("Школа", "count")},
    {"label": "Учеников на старте", "num": total_start,          "icon": "👥", "color": "#2563eb",
     "sep": True, "series": _trend("Старт")},
    {"label": "Дошли до финала",    "num": total_finish,         "icon": "🎓", "color": "#22c55e",
     "sep": True, "series": _trend("Финиш")},
    {"label": "Средний отсев",      "num": avg_dropout,          "icon": "📉", "color": "#ef4444",
     "dec": 1, "suf": "%", "series": _trend("Отсев %", "mean")},
    {"label": "Штрафов назначено",  "num": total_fines_assigned, "icon": "📋", "color": "#ef4444",
     "sep": True, "suf": "₽", "series": _trend("Штрафов назначено ₽")},
    {"label": "Оплачено всего",     "num": total_fines,          "icon": "⚠️", "color": "#f97316",
     "sep": True, "suf": "₽", "series": _trend("Штрафы ₽")},
]

# Рейтинг общий по всем потокам, к потоку не привязан — тренда по нему нет.
# Если оценок нет вообще — карточку не показываем (иначе счётчик нарисует «0.00»),
# об этом уже сообщает плитка рейтинга в шапке.
if avg_rating is not None:
    kpis.append({"label": "Средний рейтинг", "num": avg_rating, "icon": "⭐",
                 "color": rating_color(avg_rating), "dec": 2, "series": []})

rated_count = int(summary["Рейтинг"].notna().sum())
high_rated  = int((summary["Рейтинг"] >= RATING_EXCELLENT).sum())
trend_note = (
    f"Тренд на спарклайнах: потоки {hist_streams[0]}–{hist_streams[-1]}"
    if len(hist_streams) >= 2 else
    "Тренд появится, когда наберётся 2+ потока"
)

components.html(
    bento_header_html(
        title="Сводный дашборд",
        subtitle=f"{cluster_label} · Поток {selected_stream}",
        kpis=kpis,
        avg_rating=avg_rating,
        rating_note=(f"{high_rated} из {rated_count} школ с оценкой ≥ {RATING_EXCELLENT}"
                     if rated_count else "Нет оценок"),
        rating_color=rating_color(avg_rating),
        rating_verdict=rating_verdict(avg_rating),
        schools_note=f"{len(summary)} школ · поток {selected_stream}",
        trend_note=trend_note,
        # Когда выбран конкретный кластер — красим шапку в его фирменный цвет
        accent=(cluster_color(selected_cluster)
                if selected_cluster != "Все кластеры" else DEFAULT_ACCENT),
        pill=({"text": selected_cluster, "color": cluster_color(selected_cluster)}
              if selected_cluster != "Все кластеры" else None),
    ),
    height=290,
    # См. комментарий на странице школы: страховка от обрезания на узком экране
    scrolling=True,
)

st.divider()

# ─── Таблица школ ────────────────────────────────────────────────────────────
st.markdown("#### 📋 Все школы")

total_start_sum    = int(summary["Старт"].sum())
total_finish_sum   = int(summary["Финиш"].sum())
total_assigned_sum = int(summary["Штрафов назначено ₽"].sum())
total_paid_sum     = int(summary["Штрафы ₽"].sum())
avg_per_start  = int(round(total_assigned_sum / total_start_sum))  if total_start_sum  > 0 else 0
avg_per_finish = int(round(total_assigned_sum / total_finish_sum)) if total_finish_sum > 0 else 0
avg_dropout_val = round(summary["Отсев %"].mean(), 1)
avg_minutka_val = round(summary["Минутка %"].mean(), 1)
avg_rating_val  = round(summary["Рейтинг"].mean(), 2) if summary["Рейтинг"].notna().any() else None

_TH = ("position:sticky;top:0;background:#f8fafc;padding:8px 12px;text-align:left;"
       "font-size:13px;color:#1e293b;font-weight:700;border-bottom:2px solid #e2e8f0;"
       "white-space:nowrap;z-index:2;cursor:pointer;user-select:none")
_TD = "padding:6px 12px;font-size:13px;border-bottom:1px solid #f1f5f9;white-space:nowrap"
_TF = ("padding:8px 12px;font-size:13px;font-weight:700;color:#1e293b;"
       "position:sticky;bottom:0;background:#eff6ff;"
       "border-top:2px solid #2563eb;z-index:2;white-space:nowrap")

_heads = ["Школа","Кластер","Старт","Финиш","Отсев %","Назначено ₽",
          "Штрафы ₽","На 1 уч. (старт)","На 1 уч. (финиш)","Минутка %","Рейтинг"]
_cols  = ["Школа","Кластер","Старт","Финиш","Отсев %","Штрафов назначено ₽",
          "Штрафы ₽","На 1 ученика (старт)","На 1 ученика (финиш)","Минутка %","Рейтинг"]
_rub   = {"Штрафы ₽","Штрафов назначено ₽","На 1 ученика (старт)","На 1 ученика (финиш)"}

def _r(x): return f"{int(x):,}₽".replace(",", " ")

_th = "".join(
    f'<th style="{_TH}" onclick="sortTable({i})">'
    f'{h}<span class="arr" style="font-size:10px;color:#94a3b8;margin-left:4px">⇅</span></th>'
    for i, h in enumerate(_heads)
)

def _dropout_color(v) -> str:
    if pd.isna(v):
        return "#334155"
    return "#ef4444" if v >= 25 else "#f97316" if v >= 15 else "#22c55e"


def _rating_color(v) -> str:
    return rating_color(None if pd.isna(v) else v)


_tbody = ""
for _i, (_, _row) in enumerate(summary.iterrows()):
    _bg = "#fff" if _i % 2 == 0 else "#f8fafc"
    _tds = ""
    for _c in _cols:
        _v = _row[_c]
        _extra = ""
        if _c == "Кластер":
            _name = str(_v) if pd.notna(_v) else ""
            _col = cluster_color(_name)
            _tds += (f'<td style="{_TD}"><span class="pill" '
                     f'style="background:{_col}18;color:{_col}">{escape(_name)}</span></td>')
            continue
        if _c in _rub:
            _v = _r(_v)
        elif _c == "Отсев %":
            _extra = f"color:{_dropout_color(_v)};font-weight:700"
            _v = f"{_v}%"
        elif _c == "Минутка %":
            _v = f"{_v}%"
        elif _c == "Рейтинг":
            _extra = f"color:{_rating_color(_v)};font-weight:700"
            _v = f"{_v:.2f}" if pd.notna(_v) else "—"
        else:
            _v = str(_v) if pd.notna(_v) else ""
        _tds += f'<td style="{_TD};{_extra}">{escape(str(_v))}</td>'
    _tbody += f'<tr style="background:{_bg}">{_tds}</tr>'

_fvals = [
    "Среднее по потоку", "",
    str(total_start_sum), str(total_finish_sum),
    f"{avg_dropout_val}%",
    _r(total_assigned_sum), _r(total_paid_sum),
    _r(avg_per_start), _r(avg_per_finish),
    f"{avg_minutka_val}%",
    f"{avg_rating_val:.2f}" if avg_rating_val is not None else "—",
]
_tfoot = "".join(f'<td style="{_TF}">{escape(v)}</td>' for v in _fvals)

_js = (
    "<script>"
    "function sortTable(idx){"
    "var t=document.getElementById('t');"
    "var rows=Array.from(t.tBodies[0].rows);"
    "var ths=t.tHead.rows[0].cells;"
    "var th=ths[idx];"
    "var dir=th.dataset.dir==='asc'?'desc':'asc';"
    "for(var i=0;i<ths.length;i++){"
    "ths[i].dataset.dir='';"
    "var a=ths[i].querySelector('.arr');"
    "if(a)a.textContent='⇅';}"
    "th.dataset.dir=dir;"
    "var a=th.querySelector('.arr');"
    "if(a)a.textContent=dir==='asc'?'▲':'▼';"
    "function val(row){"
    "var txt=row.cells[idx].textContent.trim();"
    "var n=parseFloat(txt.replace(/[^0-9.]/g,''));"
    "return isNaN(n)?txt.toLowerCase():n;}"
    "rows.sort(function(a,b){"
    "var av=val(a),bv=val(b);"
    "if(typeof av==='number'&&typeof bv==='number')"
    "return dir==='asc'?av-bv:bv-av;"
    "return dir==='asc'?(av<bv?-1:av>bv?1:0):(bv<av?-1:bv>av?1:0);});"
    "var reduce=window.matchMedia&&"
    "window.matchMedia('(prefers-reduced-motion: reduce)').matches;"
    "rows.forEach(function(r,i){"
    "t.tBodies[0].appendChild(r);"
    "if(!reduce&&r.animate)r.animate("
    "[{opacity:0.35,transform:'translateY(6px)'},{opacity:1,transform:'none'}],"
    "{duration:340,delay:Math.min(i,14)*22,easing:'cubic-bezier(.16,1,.3,1)'});});}"
    "</script>"
)

_iframe_h = min(580, 48 + len(summary) * 38 + 48) + 4

_html = (
    '<!DOCTYPE html><html><head><meta charset="utf-8">'
    '<style>body{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}'
    'table{font-variant-numeric:tabular-nums}'
    'tbody tr{transition:background .2s ease,box-shadow .2s ease}'
    'tbody tr:hover{background:#eff6ff!important;box-shadow:inset 3px 0 0 #2563eb}'
    'tbody tr td:first-child{font-weight:600;color:#0f172a}'
    'thead th{transition:background .2s ease,color .2s ease}'
    'thead th:hover{background:#eff6ff!important;color:#2563eb}'
    '.pill{display:inline-block;padding:2px 9px;border-radius:20px;'
    'font-size:12px;font-weight:700;white-space:nowrap}'
    '</style></head><body>'
    '<table id="t" style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0">'
    f'<thead><tr>{_th}</tr></thead>'
    f'<tbody>{_tbody}</tbody>'
    f'<tfoot><tr>{_tfoot}</tr></tfoot>'
    '</table>' + _js + '</body></html>'
)

components.html(_html, height=_iframe_h, scrolling=True)

st.divider()

# ─── Отсев и штрафы по школам ────────────────────────────────────────────────
BARS_VISIBLE = 10   # столько баров видно сразу, остальные — под «Показать все»


def _render_bars(rows: list[str]) -> None:
    """Первые BARS_VISIBLE баров сразу, хвост — в раскрывающемся блоке."""
    st.markdown("".join(rows[:BARS_VISIBLE]), unsafe_allow_html=True)
    if len(rows) > BARS_VISIBLE:
        with st.expander(f"Ещё {len(rows) - BARS_VISIBLE} школ"):
            st.markdown("".join(rows[BARS_VISIBLE:]), unsafe_allow_html=True)


col_left, col_right = st.columns(2)

with col_left:
    with st.container(border=True):
        st.markdown('<div class="sec-title">📉 % отсева по школам</div>', unsafe_allow_html=True)
        sorted_dropout = summary.sort_values("Отсев %", ascending=False)
        max_d = sorted_dropout["Отсев %"].max() or 1
        rows_d = []
        for _, row in sorted_dropout.iterrows():
            val = row["Отсев %"]
            color = "red" if val >= 25 else "orange" if val >= 15 else "green"
            rows_d.append(bar_row(row["Школа"], val, max_d, f"{val}%", color))
        _render_bars(rows_d)

with col_right:
    with st.container(border=True):
        st.markdown('<div class="sec-title">⚠️ Штрафы по школам</div>', unsafe_allow_html=True)
        sorted_fines = summary.sort_values("Штрафы ₽", ascending=False)
        max_f = sorted_fines["Штрафы ₽"].max() or 1
        rows_f = []
        for _, row in sorted_fines.iterrows():
            amount = int(row["Штрафы ₽"])
            if amount > 0:
                rows_f.append(bar_row(row["Школа"], amount, max_f,
                                      f"{amount:,}₽".replace(",", " "), "orange"))
        if rows_f:
            _render_bars(rows_f)
        else:
            st.success("Штрафов нет")

# ─── Минутка дарования по школам ─────────────────────────────────────────────
with st.container(border=True):
    st.markdown('<div class="sec-title">✨ Минутка дарования по школам</div>',
                unsafe_allow_html=True)
    sorted_mk = summary.sort_values("Минутка %", ascending=False)
    cols = st.columns(2)
    half = (len(sorted_mk) + 1) // 2
    for i, (_, row) in enumerate(sorted_mk.iterrows()):
        col = cols[0] if i < half else cols[1]
        mk_val = row["Минутка %"] if pd.notna(row["Минутка %"]) else 0.0
        with col:
            st.markdown(
                bar_row(row["Школа"], mk_val, 100, f"{mk_val}%", "green"),
                unsafe_allow_html=True
            )

# ─── Рейтинг школ (NPS) ───────────────────────────────────────────────────────
with st.container(border=True):
    st.markdown('<div class="sec-title">⭐ Рейтинг школ</div>', unsafe_allow_html=True)
    rated = summary[summary["Рейтинг"].notna()].sort_values("Рейтинг", ascending=False)

    if len(rated) > 0:
        cols_r = st.columns(2)
        half_r = (len(rated) + 1) // 2
        for i, (_, row) in enumerate(rated.iterrows()):
            col = cols_r[0] if i < half_r else cols_r[1]
            r_val = row["Рейтинг"]
            color = rating_bar_class(r_val)
            with col:
                st.markdown(
                    bar_row(row["Школа"], r_val, 10, f"{r_val:.2f}", color),
                    unsafe_allow_html=True
                )
        not_rated = summary[summary["Рейтинг"].isna()]["Школа"].tolist()
        if not_rated:
            st.markdown(
                f"<div style='margin-top:8px;font-size:0.7rem;color:#94a3b8'>Пока нет отзывов: "
                f"{escape(', '.join(not_rated))}</div>",
                unsafe_allow_html=True
            )
    else:
        st.info("Пока нет отзывов по школам этого потока")

st.divider()

# ─── Штрафы по причинам (все школы) ─────────────────────────────────────────
st.markdown("#### 📋 Штрафы по причинам")

fines_detail = load_all_fines_detail(selected_stream)

# Применяем те же фильтры, что и для summary
if selected_cluster != "Все кластеры" and len(fines_detail) > 0:
    fines_detail = fines_detail[fines_detail["Кластер"] == selected_cluster]
if selected_school_filter != "Все школы" and len(fines_detail) > 0:
    fines_detail = fines_detail[fines_detail["Школа"] == selected_school_filter]

if len(fines_detail) > 0:
    by_reason = (
        fines_detail.groupby("Причина штрафа")["Сумма погашения"]
        .sum()
        .sort_values(ascending=False)
    )
    # Фильтруем нулевые и мусорные значения
    by_reason = by_reason[
        (by_reason > 0) &
        (~by_reason.index.str.lower().isin(["nan", "none", "", "-"]))
    ]

    if len(by_reason) > 0:
        max_reason = by_reason.max()
        col_l, col_r = st.columns(2)
        half_r = (len(by_reason) + 1) // 2
        bars_html_l = bars_html_r = ""
        for i, (reason, amount) in enumerate(by_reason.items()):
            html = bar_row(reason, amount, max_reason,
                           f"{int(amount):,}₽".replace(",", " "), "orange")
            if i < half_r:
                bars_html_l += html
            else:
                bars_html_r += html
        with col_l:
            st.markdown(bars_html_l, unsafe_allow_html=True)
        with col_r:
            if bars_html_r:
                st.markdown(bars_html_r, unsafe_allow_html=True)
    else:
        st.success("Штрафов нет")
else:
    st.success("Штрафов нет")

# ─── Критерии лучшей школы потока ────────────────────────────────────────────
with st.container(border=True):
    st.markdown('<div class="sec-title">🏆 Критерии лучшей школы потока</div>',
                unsafe_allow_html=True)
    try:
        card = load_scorecard()
    except Exception as e:
        card = {"data": pd.DataFrame(), "criteria": [], "filled": False}
        st.caption(f"Чек-лист недоступен: {e}")

    if card["filled"] and len(card["data"]):
        board = card["data"].copy()
        sort_col = "Итог" if "Итог" in board.columns and board["Итог"].notna().any() else "Отмечено"
        board = board.sort_values(sort_col, ascending=False)
        show = ["Школа", "Отмечено"] + (["Итог"] if "Итог" in board.columns else [])
        st.dataframe(board[show], use_container_width=True, hide_index=True)
        st.caption(
            f"Всего критериев: {len(card['criteria'])}. «Итог» берётся из таблицы "
            "руководителя кластера как есть и здесь не пересчитывается."
        )
        with st.expander("Показать список критериев"):
            st.markdown(criteria_html(card["criteria"] or None), unsafe_allow_html=True)
    else:
        st.markdown(criteria_html(card["criteria"] or None), unsafe_allow_html=True)
        st.caption(
            "Галочки проставляет руководитель кластера в отдельной таблице. "
            "По этому потоку она ещё не заполнена — рейтинг появится здесь автоматически."
        )

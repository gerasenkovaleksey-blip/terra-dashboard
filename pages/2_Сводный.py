import streamlit as st
import pandas as pd
from html import escape
from components.theme import inject_css, kpi_card, bar_row
from data.loader import load_registry, load_minutka, load_all_schools_summary, load_all_fines_detail

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

# ─── Заголовок ───────────────────────────────────────────────────────────────
cluster_label = escape(selected_cluster) if selected_cluster != "Все кластеры" else "Все кластеры"
st.markdown(f"""
<div class="terra-header">
  <div class="terra-ring"></div>
  <div>
    <div style="font-size:1.2rem;font-weight:700;color:#1e293b">Сводный дашборд</div>
    <div style="font-size:0.65rem;color:#2563eb;letter-spacing:2px;text-transform:uppercase">
        {cluster_label} · Поток {selected_stream}
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

if len(summary) == 0:
    st.warning("Нет данных за выбранный поток / кластер")
    st.stop()

# ─── KPI ─────────────────────────────────────────────────────────────────────
total_start  = int(summary["Старт"].sum())
total_finish = int(summary["Финиш"].sum())
avg_dropout  = round(summary["Отсев %"].mean(), 1)
total_fines          = int(summary["Штрафы ₽"].sum())
total_fines_assigned = int(summary["Штрафов назначено ₽"].sum())

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.markdown(kpi_card("Школ в потоке", str(len(summary)), "#2563eb", "🏫"), unsafe_allow_html=True)
with c2:
    st.markdown(kpi_card("Учеников на старте", str(total_start), "#2563eb", "👥"), unsafe_allow_html=True)
with c3:
    st.markdown(kpi_card("Дошли до финала", str(total_finish), "#22c55e", "🎓"), unsafe_allow_html=True)
with c4:
    st.markdown(kpi_card("Средний отсев", f"{avg_dropout}%", "#ef4444", "📉"), unsafe_allow_html=True)
with c5:
    st.markdown(kpi_card("Штрафов назначено", f"{total_fines_assigned:,}₽".replace(",", "\u00a0"), "#ef4444", "📋"), unsafe_allow_html=True)
with c6:
    st.markdown(kpi_card("Штрафы всего", f"{total_fines:,}₽".replace(",", "\u00a0"), "#f97316", "⚠️"), unsafe_allow_html=True)

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

_H = ("position:sticky;top:0;background:#f8fafc;padding:8px 12px;text-align:left;"
      "font-size:13px;color:#1e293b;font-weight:700;border-bottom:2px solid #e2e8f0;"
      "white-space:nowrap;z-index:2")
_D = "padding:6px 12px;font-size:13px;border-bottom:1px solid #f1f5f9;white-space:nowrap"
_F = ("padding:8px 12px;font-size:13px;font-weight:700;color:#1e293b;"
      "position:sticky;bottom:0;background:#eff6ff;"
      "border-top:2px solid #2563eb;z-index:2;white-space:nowrap")

_heads = ["Школа","Кластер","Старт","Финиш","Отсев %","Назначено ₽",
          "Штрафы ₽","На 1 уч. (старт)","На 1 уч. (финиш)","Минутка %"]
_cols  = ["Школа","Кластер","Старт","Финиш","Отсев %","Штрафов назначено ₽",
          "Штрафы ₽","На 1 ученика (старт)","На 1 ученика (финиш)","Минутка %"]
_rub   = {"Штрафы ₽","Штрафов назначено ₽","На 1 ученика (старт)","На 1 ученика (финиш)"}

def _r(x): return f"{int(x):,}₽".replace(",", " ")

_th = "".join(f'<th style="{_H}">{h}</th>' for h in _heads)

_tbody = ""
for _i, (_, _row) in enumerate(summary.iterrows()):
    _bg = "#fff" if _i % 2 == 0 else "#f8fafc"
    _tds = ""
    for _c in _cols:
        _v = _row[_c]
        if _c in _rub:       _v = _r(_v)
        elif _c == "Отсев %": _v = f"{_v}%"
        elif _c == "Минутка %": _v = f"{_v}%"
        else: _v = str(_v) if pd.notna(_v) else ""
        _tds += f'<td style="{_D}">{escape(str(_v))}</td>'
    _tbody += f'<tr style="background:{_bg}">{_tds}</tr>'

_fvals = [
    "Среднее по потоку", "",
    str(total_start_sum), str(total_finish_sum),
    f"{avg_dropout_val}%",
    _r(total_assigned_sum), _r(total_paid_sum),
    _r(avg_per_start), _r(avg_per_finish),
    f"{avg_minutka_val}%",
]
_tfoot = "".join(f'<td style="{_F}">{escape(v)}</td>' for v in _fvals)

st.markdown(
    f'<div style="max-height:560px;overflow-y:auto;border:1px solid #e2e8f0;'
    f'border-radius:8px;margin-bottom:4px">'
    f'<table style="width:100%;border-collapse:collapse">'
    f'<thead><tr>{_th}</tr></thead>'
    f'<tbody>{_tbody}</tbody>'
    f'<tfoot><tr>{_tfoot}</tr></tfoot>'
    f'</table></div>',
    unsafe_allow_html=True
)

st.divider()

# ─── Отсев и штрафы по школам ────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### 📉 % отсева по школам")
    sorted_dropout = summary.sort_values("Отсев %", ascending=False)
    max_d = sorted_dropout["Отсев %"].max() or 1
    bars_html = ""
    for _, row in sorted_dropout.iterrows():
        val = row["Отсев %"]
        color = "red" if val >= 25 else "orange" if val >= 15 else "green"
        bars_html += bar_row(row["Школа"], val, max_d, f"{val}%", color)
    st.markdown(bars_html, unsafe_allow_html=True)

with col_right:
    st.markdown("#### ⚠️ Штрафы по школам")
    sorted_fines = summary.sort_values("Штрафы ₽", ascending=False)
    max_f = sorted_fines["Штрафы ₽"].max() or 1
    bars_html = ""
    for _, row in sorted_fines.iterrows():
        amount = int(row["Штрафы ₽"])
        if amount > 0:
            bars_html += bar_row(row["Школа"], amount, max_f,
                                 f"{amount:,}₽".replace(",", "\u00a0"), "orange")
    if bars_html:
        st.markdown(bars_html, unsafe_allow_html=True)
    else:
        st.success("Штрафов нет")

st.divider()

# ─── Минутка дарования по школам ─────────────────────────────────────────────
st.markdown("#### ✨ Минутка дарования по школам")
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
        fines_detail.groupby("Причина штрафа")["Сумма штрафа"]
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
                           f"{int(amount):,}₽".replace(",", " "), "orange")
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

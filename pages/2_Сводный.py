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

# Compute weighted averages for per-student columns before formatting
total_start_sum    = summary["Старт"].sum()
total_finish_sum   = summary["Финиш"].sum()
total_assigned_sum = summary["Штрафов назначено ₽"].sum()
total_paid_sum     = summary["Штрафы ₽"].sum()
avg_per_start  = int(round(total_assigned_sum / total_start_sum))  if total_start_sum  > 0 else 0
avg_per_finish = int(round(total_assigned_sum / total_finish_sum)) if total_finish_sum > 0 else 0

display_df = summary[["Школа", "Кластер", "Старт", "Финиш", "Отсев %", "Штрафы ₽",
                       "Штрафов назначено ₽", "На 1 ученика (старт)", "На 1 ученика (финиш)",
                       "Минутка %"]].copy()
display_df["Штрафы ₽"]               = display_df["Штрафы ₽"].apply(lambda x: f"{int(x):,}₽".replace(",", "\u00a0"))
display_df["Штрафов назначено ₽"]     = display_df["Штрафов назначено ₽"].apply(lambda x: f"{int(x):,}₽".replace(",", "\u00a0"))
display_df["На 1 ученика (старт)"]    = display_df["На 1 ученика (старт)"].apply(lambda x: f"{int(x):,}₽".replace(",", "\u00a0"))
display_df["На 1 ученика (финиш)"]    = display_df["На 1 ученика (финиш)"].apply(lambda x: f"{int(x):,}₽".replace(",", "\u00a0"))
display_df["Отсев %"]                = display_df["Отсев %"].apply(lambda x: f"{x}%")
display_df["Минутка %"]              = display_df["Минутка %"].apply(lambda x: f"{x}%")

# Average row
avg_row = pd.DataFrame([{
    "Школа": "Среднее по потоку", "Кластер": "",
    "Старт": total_start_sum, "Финиш": total_finish_sum,
    "Отсев %": f"{round(summary['Отсев %'].mean(), 1)}%",
    "Штрафы ₽": f"{int(total_paid_sum):,}₽".replace(",", "\u00a0"),
    "Штрафов назначено ₽": f"{int(total_assigned_sum):,}₽".replace(",", "\u00a0"),
    "На 1 ученика (старт)": f"{avg_per_start:,}₽".replace(",", "\u00a0"),
    "На 1 ученика (финиш)": f"{avg_per_finish:,}₽".replace(",", "\u00a0"),
    "Минутка %": f"{round(summary['Минутка %'].mean(), 1)}%",
}])
display_df = pd.concat([display_df, avg_row], ignore_index=True)
st.dataframe(display_df, use_container_width=True, hide_index=True)

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

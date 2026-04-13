import streamlit as st
import pandas as pd
from html import escape
from components.theme import inject_css, kpi_card, bar_row
from data.loader import load_registry, load_minutka, load_all_schools_summary

st.set_page_config(page_title="TERRA · Сводный", page_icon="📊", layout="wide")
inject_css()

# ─── Sidebar ─────────────────────────────────────────────────────────────────
registry = load_registry()

def _get_all_streams() -> list[int]:
    """Собираем все потоки из первой доступной школы."""
    for _, row in registry.iterrows():
        sid = row["sheet_id"]
        if not sid:
            continue
        try:
            m = load_minutka(sid)
            return sorted(m["Поток"].dropna().astype(int).unique().tolist(), reverse=True)
        except Exception:
            continue
    return []

with st.sidebar:
    st.markdown("### ⭕ TERRA")
    streams = _get_all_streams()
    if not streams:
        st.warning("Нет данных по потокам")
        st.stop()
    selected_stream = st.selectbox("Поток", streams)

    clusters = ["Все кластеры"] + sorted(registry["Кластер"].dropna().unique().tolist())
    selected_cluster = st.selectbox("Кластер", clusters)

    if st.button("🔄 Обновить данные"):
        st.cache_data.clear()
        st.rerun()

# ─── Загрузка сводных данных ─────────────────────────────────────────────────
with st.spinner("Загрузка данных всех школ..."):
    summary = load_all_schools_summary(selected_stream)

if selected_cluster != "Все кластеры":
    summary = summary[summary["Кластер"] == selected_cluster]

# ─── Заголовок ───────────────────────────────────────────────────────────────
cluster_label = escape(selected_cluster) if selected_cluster != "Все кластеры" else "Все кластеры"
st.markdown(f"""
<div class="terra-header">
  <div class="terra-ring"></div>
  <div>
    <div style="font-size:1.2rem;font-weight:700;color:#f0f4ff">Сводный дашборд</div>
    <div style="font-size:0.65rem;color:#4a9eff;letter-spacing:2px;text-transform:uppercase">
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
avg_dropout  = round((total_start - total_finish) / total_start * 100, 1) if total_start > 0 else 0.0
total_fines  = int(summary["Штрафы ₽"].sum())

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.markdown(kpi_card("Школ в потоке", str(len(summary)), "#4a9eff", "🏫"), unsafe_allow_html=True)
with c2:
    st.markdown(kpi_card("Учеников на старте", str(total_start), "#4a9eff", "👥"), unsafe_allow_html=True)
with c3:
    st.markdown(kpi_card("Дошли до финала", str(total_finish), "#40e090", "🎓"), unsafe_allow_html=True)
with c4:
    st.markdown(kpi_card("Средний отсев", f"{avg_dropout}%", "#ff5070", "📉"), unsafe_allow_html=True)
with c5:
    st.markdown(kpi_card("Штрафы всего", f"{total_fines:,}₽".replace(",", "\u00a0"), "#ffa040", "⚠️"), unsafe_allow_html=True)

st.divider()

# ─── Таблица школ ────────────────────────────────────────────────────────────
st.markdown("#### 📋 Все школы")

display_df = summary[["Школа", "Кластер", "Старт", "Финиш", "Отсев %", "Штрафы ₽", "Минутка %"]].copy()
display_df["Штрафы ₽"]  = display_df["Штрафы ₽"].apply(lambda x: f"{int(x):,}₽".replace(",", "\u00a0"))
display_df["Отсев %"]   = display_df["Отсев %"].apply(lambda x: f"{x}%")
display_df["Минутка %"] = display_df["Минутка %"].apply(lambda x: f"{x}%")
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
        color = "red" if val > 25 else "orange" if val > 15 else "green"
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
    with col:
        st.markdown(
            bar_row(row["Школа"], row["Минутка %"], 100, f"{row['Минутка %']}%", "green"),
            unsafe_allow_html=True
        )

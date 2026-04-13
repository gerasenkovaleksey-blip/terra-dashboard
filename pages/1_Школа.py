import streamlit as st
import pandas as pd
from html import escape
from components.theme import inject_css, kpi_card, bar_row
from data.loader import load_registry, load_minutka, load_fines, school_metrics

st.set_page_config(page_title="TERRA · Школа", page_icon="🏫", layout="wide")
inject_css()

# ─── Sidebar ─────────────────────────────────────────────────────────────────
registry = load_registry()
school_names = registry["Школа"].tolist()  # "Школа", не "Название школы"

with st.sidebar:
    st.markdown("### ⭕ TERRA")
    selected_school = st.selectbox("Школа", school_names)

school_row = registry[registry["Школа"] == selected_school].iloc[0]
sheet_id   = school_row["sheet_id"]
cluster    = school_row["Кластер"] if pd.notna(school_row["Кластер"]) else "—"

minutka_df = load_minutka(sheet_id)
fines_df   = load_fines(sheet_id)

# Список потоков из реальных данных
streams = sorted(
    minutka_df["Поток"].dropna().astype(int).unique().tolist(), reverse=True
)

with st.sidebar:
    selected_stream = st.selectbox("Поток", streams if streams else [0])
    if st.button("🔄 Обновить данные"):
        st.cache_data.clear()
        st.rerun()

metrics = school_metrics(minutka_df, fines_df, selected_stream)

# ─── Заголовок ───────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="terra-header">
  <div class="terra-ring"></div>
  <div>
    <div style="font-size:1.2rem;font-weight:700;color:#f0f4ff">{escape(selected_school)}</div>
    <div style="font-size:0.65rem;color:#4a9eff;letter-spacing:2px;text-transform:uppercase">
        Кластер: {escape(str(cluster))} · Поток {selected_stream}
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── KPI карточки ────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.markdown(kpi_card("Пришли на 1-е занятие", str(metrics["first_lesson_students"]), "#4a9eff", "👥"), unsafe_allow_html=True)
with c2:
    st.markdown(kpi_card("Дошли до последнего", str(metrics["last_lesson_students"]), "#4a9eff", "🎓"), unsafe_allow_html=True)
with c3:
    st.markdown(kpi_card("% отсева", f"{metrics['dropout_pct']}%", "#ff5070", "📉"), unsafe_allow_html=True)
with c4:
    total = int(metrics["total_fines"])
    st.markdown(kpi_card("Сумма штрафов", f"{total:,}₽".replace(",", "\u00a0"), "#ffa040", "⚠️"), unsafe_allow_html=True)
with c5:
    st.markdown(kpi_card("Минутка дарования", f"{metrics['avg_minutka_pct']}%", "#40e090", "✨"), unsafe_allow_html=True)

st.divider()

# ─── Воронка отсева ───────────────────────────────────────────────────────────
st.markdown("#### 📉 Воронка отсева")
first = metrics["first_lesson_students"]
last  = metrics["last_lesson_students"]
dropped = first - last
dropout_pct = metrics["dropout_pct"]

funnel_html = f"""
<div style="display:flex;align-items:center;gap:24px;padding:16px 0">
  <div style="text-align:center;flex:1">
    <div style="font-size:2.5rem;font-weight:800;color:#4a9eff">{first}</div>
    <div style="font-size:0.65rem;color:#3a5070;text-transform:uppercase;letter-spacing:1px">Старт</div>
  </div>
  <div style="font-size:1.5rem;color:#1a2a40">→</div>
  <div style="text-align:center;flex:2">
    <div style="font-size:0.75rem;color:#ff5070;font-weight:700">−{escape(str(dropped))} чел. ({escape(str(dropout_pct))}%)</div>
    <div style="background:#0f1828;border-radius:4px;height:6px;margin:8px 0;position:relative;overflow:hidden">
      <div style="position:absolute;left:0;top:0;height:100%;width:{100 - dropout_pct:.0f}%;background:linear-gradient(90deg,#1a4080,#4a9eff)"></div>
    </div>
    <div style="font-size:0.65rem;color:#3a5070">Осталось {100 - dropout_pct:.0f}%</div>
  </div>
  <div style="font-size:1.5rem;color:#1a2a40">→</div>
  <div style="text-align:center;flex:1">
    <div style="font-size:2.5rem;font-weight:800;color:#40e090">{last}</div>
    <div style="font-size:0.65rem;color:#3a5070;text-transform:uppercase;letter-spacing:1px">Финиш</div>
  </div>
</div>
"""
st.markdown(funnel_html, unsafe_allow_html=True)
st.divider()

# ─── Посещаемость и штрафы ───────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### 📊 Посещаемость по занятиям")
    ml = metrics["minutka_by_lesson"]
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
    st.markdown("#### ⚠️ Штрафы по причинам")
    fbr = metrics["fines_by_reason"]
    if len(fbr) > 0:
        total_f = fbr.sum()
        bars_html = ""
        for reason, amount in fbr.items():
            if amount > 0:
                bars_html += bar_row(reason, amount, total_f or 1, f"{int(amount):,}₽".replace(",", "\u00a0"), "orange")
        st.markdown(bars_html, unsafe_allow_html=True)
        st.markdown(
            f"<div style='margin-top:12px;font-size:0.7rem;color:#3a5070'>Итого: "
            f"<b style='color:#ffa040'>{int(total_f):,}₽</b></div>".replace(",", "\u00a0"),
            unsafe_allow_html=True
        )
    else:
        st.success("Штрафов нет")

st.divider()

# ─── Минутка дарования ───────────────────────────────────────────────────────
st.markdown("#### ✨ Минутка дарования")

avg_pct = metrics["avg_minutka_pct"]
# Кольцевой график через CSS conic-gradient
ring_pct = min(100, max(0, avg_pct))
ring_color = "#40e090" if ring_pct >= 80 else "#ffa040" if ring_pct >= 50 else "#ff5070"
ring_html = f"""
<div style="display:flex;align-items:center;gap:24px;margin-bottom:16px">
  <div style="position:relative;width:80px;height:80px;flex-shrink:0">
    <div style="width:80px;height:80px;border-radius:50%;background:conic-gradient({ring_color} 0% {ring_pct:.0f}%, #0f1828 {ring_pct:.0f}% 100%)"></div>
    <div style="position:absolute;inset:8px;border-radius:50%;background:#060a12;display:flex;align-items:center;justify-content:center">
      <span style="font-size:0.85rem;font-weight:800;color:{ring_color}">{avg_pct:.0f}%</span>
    </div>
  </div>
  <div>
    <div style="font-size:1rem;font-weight:700;color:{ring_color}">{avg_pct:.1f}%</div>
    <div style="font-size:0.65rem;color:#3a5070;text-transform:uppercase;letter-spacing:1px">Средний % за поток</div>
  </div>
</div>
"""
st.markdown(ring_html, unsafe_allow_html=True)

st.markdown("**По занятиям:**")
ml = metrics["minutka_by_lesson"]
if len(ml) > 0:
    bars_html = ""
    for _, row in ml.iterrows():
        pct = float(row["Процент выполнения"]) if pd.notna(row["Процент выполнения"]) else 0.0
        bars_html += bar_row(f"Занятие {int(row['Занятие'])}", pct, 100, f"{pct:.1f}%", "green")
    st.markdown(bars_html, unsafe_allow_html=True)
else:
    st.info("Нет данных")

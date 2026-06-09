import streamlit as st
import pandas as pd
from html import escape
from components.theme import inject_css, kpi_card, bar_row
from data.loader import load_registry, load_minutka, load_fines, school_metrics

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

# ─── Заголовок ───────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="terra-header">
  <div class="terra-ring"></div>
  <div>
    <div style="font-size:1.2rem;font-weight:700;color:#1e293b">{escape(selected_school)}</div>
    <div style="font-size:0.65rem;color:#2563eb;letter-spacing:2px;text-transform:uppercase">
        Кластер: {escape(str(cluster))} · Поток {selected_stream}
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── KPI карточки ────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    st.markdown(kpi_card("Пришли на 1-е занятие", str(metrics["first_lesson_students"]), "#2563eb", "👥"), unsafe_allow_html=True)
with c2:
    st.markdown(kpi_card("Дошли до последнего", str(metrics["last_lesson_students"]), "#2563eb", "🎓"), unsafe_allow_html=True)
with c3:
    st.markdown(kpi_card("% отсева", f"{metrics['dropout_pct']}%", "#ef4444", "📉"), unsafe_allow_html=True)
with c4:
    assigned = int(metrics["total_fines"])
    st.markdown(kpi_card("Штрафов назначено", f"{assigned:,}₽".replace(",", "\u00a0"), "#ef4444", "📋"), unsafe_allow_html=True)
with c5:
    paid = int(metrics["total_fines_paid"])
    st.markdown(kpi_card("Штрафы оплачены", f"{paid:,}₽".replace(",", "\u00a0"), "#f97316", "⚠️"), unsafe_allow_html=True)
with c6:
    st.markdown(kpi_card("Минутка дарования", f"{metrics['avg_minutka_pct']}%", "#22c55e", "✨"), unsafe_allow_html=True)

st.divider()

# ─── Воронка отсева ──────────────────────────────────────────────────────────
st.markdown("#### 📉 Воронка отсева")
first = metrics["first_lesson_students"]
last  = metrics["last_lesson_students"]
dropout_pct = metrics["dropout_pct"]

if first > 0:
    dropped = first - last
    remaining_pct = max(0, min(100, 100 - dropout_pct))
    funnel_html = f"""
<div style="display:flex;align-items:center;gap:24px;padding:16px 0">
  <div style="text-align:center;flex:1">
    <div style="font-size:2.5rem;font-weight:800;color:#2563eb">{first}</div>
    <div style="font-size:0.65rem;color:#94a3b8;text-transform:uppercase;letter-spacing:1px">Старт</div>
  </div>
  <div style="font-size:1.5rem;color:#cbd5e1">→</div>
  <div style="text-align:center;flex:2">
    <div style="font-size:0.75rem;color:#ef4444;font-weight:700">−{dropped} чел. ({max(0, dropout_pct):.1f}%)</div>
    <div style="background:#e2e8f0;border-radius:4px;height:6px;margin:8px 0;position:relative;overflow:hidden">
      <div style="position:absolute;left:0;top:0;height:100%;width:{remaining_pct:.0f}%;background:linear-gradient(90deg,#1d4ed8,#60a5fa)"></div>
    </div>
    <div style="font-size:0.65rem;color:#94a3b8">Осталось {remaining_pct:.0f}%</div>
  </div>
  <div style="font-size:1.5rem;color:#cbd5e1">→</div>
  <div style="text-align:center;flex:1">
    <div style="font-size:2.5rem;font-weight:800;color:#22c55e">{last}</div>
    <div style="font-size:0.65rem;color:#94a3b8;text-transform:uppercase;letter-spacing:1px">Финиш</div>
  </div>
</div>
"""
    st.markdown(funnel_html, unsafe_allow_html=True)
else:
    st.info("Нет данных по посещаемости за этот поток")

st.divider()

# ─── Посещаемость и штрафы ───────────────────────────────────────────────────
col_left, col_right = st.columns(2)
ml = metrics["minutka_by_lesson"]

with col_left:
    st.markdown("#### 📊 Посещаемость по занятиям")
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
            f"<div style='margin-top:12px;font-size:0.7rem;color:#64748b'>Итого: "
            f"<b style='color:#f97316'>{int(total_f):,}₽</b></div>".replace(",", "\u00a0"),
            unsafe_allow_html=True
        )
    else:
        st.success("Штрафов нет")

st.divider()

# ─── Минутка дарования ───────────────────────────────────────────────────────
st.markdown("#### ✨ Минутка дарования")

avg_pct = metrics["avg_minutka_pct"]
ring_pct = min(100, max(0, avg_pct))
ring_color = "#22c55e" if ring_pct >= 80 else "#f97316" if ring_pct >= 50 else "#ef4444"
ring_html = f"""
<div style="display:flex;align-items:center;gap:24px;margin-bottom:16px">
  <div style="position:relative;width:80px;height:80px;flex-shrink:0">
    <div style="width:80px;height:80px;border-radius:50%;background:conic-gradient({ring_color} 0% {ring_pct:.0f}%, #e2e8f0 {ring_pct:.0f}% 100%)"></div>
    <div style="position:absolute;inset:8px;border-radius:50%;background:#ffffff;display:flex;align-items:center;justify-content:center;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
      <span style="font-size:0.85rem;font-weight:800;color:{ring_color}">{avg_pct:.0f}%</span>
    </div>
  </div>
  <div>
    <div style="font-size:1rem;font-weight:700;color:{ring_color}">{avg_pct:.1f}%</div>
    <div style="font-size:0.65rem;color:#94a3b8;text-transform:uppercase;letter-spacing:1px">Средний % за поток</div>
  </div>
</div>
"""
st.markdown(ring_html, unsafe_allow_html=True)

st.markdown("**По занятиям:**")
if len(ml) > 0:
    bars_html = ""
    for _, row in ml.iterrows():
        pct = float(row["Процент выполнения"]) if pd.notna(row["Процент выполнения"]) else 0.0
        bars_html += bar_row(f"Занятие {int(row['Занятие'])}", pct, 100, f"{pct:.1f}%", "green")
    st.markdown(bars_html, unsafe_allow_html=True)
else:
    st.info("Нет данных")

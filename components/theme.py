import streamlit as st
from html import escape

# ─── Фирменные цвета кластеров ────────────────────────────────────────────────
# Взяты с официальной инфографики TERRA (плашки кластеров).
# Единственное место, где они заданы — используются и в таблице сводной,
# и в шапке страницы школы.
CLUSTER_COLORS: dict[str, str] = {
    "Здоровье":  "#4CA24E",
    "Стратегия": "#1F6FB2",
    "Маркетинг": "#F0632A",
    "Бизнес":    "#F7B32B",
    "Навыки":    "#7B4FA5",
    "Финансы":   "#35B5A8",
}

# Запасные цвета для кластеров, которых ещё нет в CLUSTER_COLORS
_CLUSTER_FALLBACK = ["#0284c7", "#e11d48", "#ca8a04", "#7c3aed", "#0d9488"]

DEFAULT_ACCENT = "#2563eb"

# ─── Пороги рейтинга школы (средний балл 0–10) ────────────────────────────────
# Подобраны под реальный разброс: из 1068 ответов 852 — «десятки», поэтому
# средние сжаты в диапазон 8.5–10.0. Стандартные NPS-пороги (9 и 7) красили
# зелёным 90% школ и не различали их между собой.
RATING_EXCELLENT = 9.6      # и выше — «Отлично»
RATING_GOOD      = 9.2      # 9.2–9.59 — «Хорошо», ниже — «Требует внимания»

_RATING_NA_COLOR = "#94a3b8"


def _is_na(value) -> bool:
    """True для None и NaN — без импорта pandas в тему."""
    return value is None or value != value


def rating_color(score) -> str:
    """Цвет рейтинга школы по порогам выше."""
    if _is_na(score):
        return _RATING_NA_COLOR
    if score >= RATING_EXCELLENT:
        return "#22c55e"
    return "#f97316" if score >= RATING_GOOD else "#ef4444"


def rating_verdict(score) -> str:
    """Словесная оценка рейтинга."""
    if _is_na(score):
        return "Нет данных"
    if score >= RATING_EXCELLENT:
        return "Отлично"
    return "Хорошо" if score >= RATING_GOOD else "Требует внимания"


def rating_bar_class(score) -> str:
    """Класс цвета для bar_row(): green / orange / red."""
    if _is_na(score):
        return "blue"
    if score >= RATING_EXCELLENT:
        return "green"
    return "orange" if score >= RATING_GOOD else "red"


def cluster_color(name) -> str:
    """
    Цвет кластера по названию. Незнакомые кластеры получают цвет из запасной
    палитры детерминированно (по имени), чтобы он не менялся между перерисовками.
    """
    if name is None:
        return DEFAULT_ACCENT
    key = str(name).strip()
    if key in CLUSTER_COLORS:
        return CLUSTER_COLORS[key]
    if not key or key == "—":
        return DEFAULT_ACCENT
    return _CLUSTER_FALLBACK[sum(map(ord, key)) % len(_CLUSTER_FALLBACK)]

TERRA_CSS = """
<style>
.block-container { padding-top: 3.5rem !important; padding-bottom: 5rem !important; }

/* KPI карточки — белые с цветной полосой сверху */
.kpi-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px 14px;
    text-align: center;
    position: relative;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: var(--accent);
}
.kpi-value { font-size: 2rem; font-weight: 800; line-height: 1; margin-bottom: 6px; }
.kpi-label { font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; }

/* Заголовок */
.terra-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding-bottom: 16px;
    border-bottom: 1px solid #e2e8f0;
    margin-bottom: 20px;
}
.terra-ring {
    width: 32px; height: 32px;
    border-radius: 50%;
    border: 2.5px solid #2563eb;
    flex-shrink: 0;
}

/* Горизонтальные бары */
.bar-track {
    background: #e2e8f0;
    border-radius: 4px;
    height: 8px;
    overflow: hidden;
    margin: 4px 0;
}
.bar-fill-blue   { height: 100%; background: linear-gradient(90deg, #1d4ed8, #60a5fa); border-radius: 4px; }
.bar-fill-red    { height: 100%; background: linear-gradient(90deg, #b91c1c, #f87171); border-radius: 4px; }
.bar-fill-green  { height: 100%; background: linear-gradient(90deg, #15803d, #4ade80); border-radius: 4px; }
.bar-fill-orange { height: 100%; background: linear-gradient(90deg, #c2410c, #fb923c); border-radius: 4px; }

/* Бары «вырастают» при отрисовке.
   Масштабируем через transform, а не width — inline-ширина остаётся нетронутой,
   поэтому bar_row() не нужно менять. */
.bar-fill-blue, .bar-fill-red, .bar-fill-green, .bar-fill-orange {
    transform-origin: left center;
    animation: barGrow 0.9s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes barGrow { from { transform: scaleX(0); } to { transform: scaleX(1); } }

/* Подсветка строки бара при наведении */
.bar-row {
    padding: 2px 6px;
    border-radius: 6px;
    transition: background 0.2s ease;
}
.bar-row:hover { background: #f1f5f9; }

/* Секции-карточки (st.container(border=True)) в бенто-стиле */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 14px !important;
    border-color: #e2e8f0 !important;
    background: #ffffff;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
    transition: box-shadow 0.35s ease;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    box-shadow: 0 10px 26px rgba(15, 23, 42, 0.10);
}

/* Кольцевые gauge-виджеты (минутка, рейтинг школы).
   ВАЖНО: сам conic-gradient задаётся инлайном с готовыми значениями.
   Streamlit прогоняет HTML из st.markdown через санитайзер, который вырезает
   CSS-переменные (--c, --pct) из атрибута style — поэтому вариант с var()
   тут не работает, проверено. Анимация — появление, а не «дозаливка». */
.gauge {
    position: relative;
    border-radius: 50%;
    flex-shrink: 0;
    animation: gaugeIn 0.7s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes gaugeIn {
    from { opacity: 0; transform: scale(0.88) rotate(-25deg); }
    to   { opacity: 1; transform: none; }
}
.gauge-hole {
    position: absolute;
    inset: 8px;
    border-radius: 50%;
    background: #ffffff;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    font-weight: 800;
    line-height: 1;
}

/* Заголовок секции внутри карточки */
.sec-title {
    font-size: 0.85rem;
    font-weight: 700;
    color: #1e293b;
    margin-bottom: 12px;
}
@media (prefers-reduced-motion: reduce) {
    .bar-fill-blue, .bar-fill-red, .bar-fill-green, .bar-fill-orange { animation: none; }
    .gauge { animation: none; }
}
</style>
"""

def inject_css():
    st.markdown(TERRA_CSS, unsafe_allow_html=True)

def kpi_card(label: str, value: str, color: str = "#2563eb", icon: str = "") -> str:
    """Returns HTML for a KPI card."""
    icon_html = f'<div style="font-size:1.2rem;margin-bottom:8px">{icon}</div>' if icon else ''
    return f"""
    <div class="kpi-card" style="--accent:{color}">
        {icon_html}
        <div class="kpi-value" style="color:{color}">{escape(str(value))}</div>
        <div class="kpi-label">{escape(str(label))}</div>
    </div>
    """

def bar_row(label: str, value: float, max_value: float, display: str, color_class: str = "blue") -> str:
    """Returns HTML for a horizontal bar row."""
    import math
    if value is None or (isinstance(value, float) and math.isnan(value)):
        value = 0.0
    pct = max(0, min(100, round(value / max_value * 100))) if max_value > 0 else 0
    color_map = {
        "blue":   "#2563eb",
        "red":    "#ef4444",
        "green":  "#22c55e",
        "orange": "#f97316",
    }
    safe_color = color_class if color_class in color_map else "blue"
    text_color = color_map[safe_color]
    return f"""
    <div class="bar-row" style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
        <div style="font-size:0.7rem;color:#64748b;width:180px;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{escape(str(label))}</div>
        <div class="bar-track" style="flex:1"><div class="bar-fill-{safe_color}" style="width:{pct}%"></div></div>
        <div style="font-size:0.75rem;font-weight:700;color:{text_color};min-width:60px;text-align:right">{escape(str(display))}</div>
    </div>
    """

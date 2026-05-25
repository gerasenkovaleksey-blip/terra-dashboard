import streamlit as st
from html import escape

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
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
        <div style="font-size:0.7rem;color:#64748b;width:180px;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{escape(str(label))}</div>
        <div class="bar-track" style="flex:1"><div class="bar-fill-{safe_color}" style="width:{pct}%"></div></div>
        <div style="font-size:0.75rem;font-weight:700;color:{text_color};min-width:60px;text-align:right">{escape(str(display))}</div>
    </div>
    """

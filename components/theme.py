import streamlit as st
from html import escape

TERRA_CSS = """
<style>
.block-container { padding-top: 1.5rem; padding-bottom: 1rem; }

.kpi-card {
    background: #0a1020;
    border: 1px solid #1a2a40;
    border-radius: 10px;
    padding: 16px 14px;
    text-align: center;
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
}
.kpi-value { font-size: 2rem; font-weight: 800; line-height: 1; margin-bottom: 6px; }
.kpi-label { font-size: 0.7rem; color: #3a5070; text-transform: uppercase; letter-spacing: 1px; }

.terra-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding-bottom: 16px;
    border-bottom: 1px solid #1a2540;
    margin-bottom: 20px;
}
.terra-ring {
    width: 32px; height: 32px;
    border-radius: 50%;
    border: 2.5px solid #4a9eff;
    box-shadow: 0 0 12px #4a9eff66;
    flex-shrink: 0;
}

.bar-track {
    background: #0f1828;
    border-radius: 4px;
    height: 8px;
    overflow: hidden;
    margin: 4px 0;
}
.bar-fill-blue   { height: 100%; background: linear-gradient(90deg, #1a4080, #4a9eff); border-radius: 4px; }
.bar-fill-red    { height: 100%; background: linear-gradient(90deg, #801a30, #e05060); border-radius: 4px; }
.bar-fill-green  { height: 100%; background: linear-gradient(90deg, #0a5030, #40e090); border-radius: 4px; }
.bar-fill-orange { height: 100%; background: linear-gradient(90deg, #804010, #ffa040); border-radius: 4px; }
</style>
"""

def inject_css():
    st.markdown(TERRA_CSS, unsafe_allow_html=True)

def kpi_card(label: str, value: str, color: str = "#4a9eff", icon: str = "") -> str:
    """Returns HTML for a KPI card."""
    icon_html = f'<div style="font-size:1.2rem;margin-bottom:8px">{icon}</div>' if icon else ''
    return f"""
    <div class="kpi-card" style="--accent:{color}">
        {icon_html}
        <div class="kpi-value" style="color:{color};text-shadow:0 0 16px {color}55">{escape(str(value))}</div>
        <div class="kpi-label">{escape(str(label))}</div>
    </div>
    """

def bar_row(label: str, value: float, max_value: float, display: str, color_class: str = "blue") -> str:
    """Returns HTML for a horizontal bar row."""
    pct = max(0, min(100, round(value / max_value * 100))) if max_value > 0 else 0
    color_map = {
        "blue": "#4a9eff",
        "red": "#ff5070",
        "green": "#40e090",
        "orange": "#ffa040",
    }
    safe_color = color_class if color_class in color_map else "blue"
    text_color = color_map[safe_color]
    return f"""
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
        <div style="font-size:0.7rem;color:#4a6080;width:180px;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{escape(str(label))}</div>
        <div class="bar-track" style="flex:1"><div class="bar-fill-{safe_color}" style="width:{pct}%"></div></div>
        <div style="font-size:0.75rem;font-weight:700;color:{text_color};min-width:60px;text-align:right">{escape(str(display))}</div>
    </div>
    """

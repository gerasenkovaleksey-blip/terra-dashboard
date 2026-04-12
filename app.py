import streamlit as st
from components.theme import inject_css

st.set_page_config(
    page_title="TERRA Дашборды",
    page_icon="⭕",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()

st.markdown("## ⭕ TERRA — Дашборды школ")
st.markdown("Выберите раздел в боковом меню слева.")

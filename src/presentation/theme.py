"""Tema visual e estilos globais da aplicação Streamlit."""

import streamlit as st


_GLOBAL_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=Montserrat:wght@600;700;800&display=swap');
    :root{
        --vava-green-dark: #0F3B2E;
        --vava-green: #145D44;
        --vava-gold: #C9A23A;
        --vava-cream: #F6F1E6;
    }
    html, body, [data-testid='stAppViewContainer'] {
        background: linear-gradient(180deg, var(--vava-green-dark) 0%, #0B2E25 100%);
        color: var(--vava-cream);
        font-family: 'Roboto', 'Segoe UI', Arial, sans-serif;
    }
    h1, h2, h3, h4, h5, h6, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Montserrat', 'Segoe UI', Arial, sans-serif;
        letter-spacing: 0.01em;
    }
    [data-testid='stMetricLabel'],
    [data-testid='stMetricValue'],
    .metric-card,
    .metric-card .card-title,
    .metric-card .card-value,
    .streamlit-expanderHeader,
    .stButton>button,
    .stDownloadButton>button,
    .stSidebar h1,
    .stSidebar h2,
    .stSidebar h3,
    .stSidebar h4,
    .stSidebar h5,
    .stSidebar h6 {
        font-family: 'Montserrat', 'Segoe UI', Arial, sans-serif;
    }
    .header {
        text-align: center;
        padding: 1.2rem 0 0.25rem 0;
    }
    .vava-logo-wrapper {
        display:flex;align-items:center;justify-content:center;margin-bottom:0.6rem;
    }
    .vava-logo {
        border-radius: 999px;
        border: 4px solid var(--vava-gold);
        box-shadow: 0 6px 18px rgba(0,0,0,0.4);
    }
    .stImage img { border-radius: 999px !important; border:4px solid var(--vava-gold) !important; box-shadow: 0 6px 18px rgba(0,0,0,0.4) !important; }
    .metric-card {
        background: linear-gradient(180deg, rgba(201,162,58,0.09), rgba(255,255,255,0.02));
        padding: 0.9rem 1rem;
        border-radius: 14px;
        margin: 0.4rem 0;
        border: 1px solid rgba(201,162,58,0.14);
        color: var(--vava-cream);
    }
    .metric-card .card-title { font-size:0.95rem; opacity:0.9; }
    .metric-card .card-value { font-size:1.25rem; font-weight:700; color: var(--vava-cream); }
    .stButton>button {
        background: linear-gradient(90deg, var(--vava-gold), #E6C46B) !important;
        color: #0b2e25 !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
    }
    .stDownloadButton>button { padding: 0.45rem 0.8rem !important; }
    .dataframe-wrapper { border-radius:12px; overflow:hidden; border:1px solid rgba(255,255,255,0.03); }
    .dataframe thead tr th { background: rgba(20,93,68,0.6) !important; }
    .streamlit-expanderHeader { color: var(--vava-cream) !important; }
</style>
"""


def apply_global_styles() -> None:
    """Aplica CSS global da aplicação."""
    st.markdown(_GLOBAL_STYLE, unsafe_allow_html=True)


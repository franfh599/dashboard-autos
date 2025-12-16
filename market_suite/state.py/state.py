# -*- coding: utf-8 -*-
"""
Market Suite | State Management Module

Handles session state initialization and figure registry for PDF export.
Previously in: app.py (monolithic)
"""

from __future__ import annotations
from typing import Dict, List, Optional
import streamlit as st

# ==============================================================================
# STATE CONSTANTS
# ==============================================================================

THEME_SYSTEM = "SYSTEM"
THEME_DARK_FORCE = "DARK_FORCE"
THEME_LIGHT_FORCE = "LIGHT_FORCE"

TIME_FULL = "FULL"
TIME_YTD = "YTD"

TIME_VIEW_LABELS = {
    "Full Year (Completo)": TIME_FULL,
    "YTD (Year to Date)": TIME_YTD,
}


# ==============================================================================
# SESSION STATE INITIALIZATION
# ==============================================================================

def init_session_state() -> None:
    """Initialize all required session state variables."""
    if "theme_mode" not in st.session_state:
        st.session_state["theme_mode"] = THEME_SYSTEM
    
    if "time_view" not in st.session_state:
        st.session_state["time_view"] = TIME_FULL
    
    if "debug_mode" not in st.session_state:
        st.session_state["debug_mode"] = False
    
    if "data_source_mode" not in st.session_state:
        st.session_state["data_source_mode"] = "AUTO"
    
    if "data_url" not in st.session_state:
        st.session_state["data_url"] = ""
    
    if "last_error" not in st.session_state:
        st.session_state["last_error"] = ""
    
    if "uploaded_parquet" not in st.session_state:
        st.session_state["uploaded_parquet"] = None
    
    # Figure registry for PDF export (CRITICAL for multipage)
    if "figure_registry" not in st.session_state:
        st.session_state["figure_registry"] = []
    
    # Menu state for navigation
    if "menu" not in st.session_state:
        st.session_state["menu"] = "🌟 1. Visión País (Macro)"


# ==============================================================================
# FIGURE REGISTRY (for PDF export with charts)
# ==============================================================================

def register_figure(fig, title: str, section: str) -> None:
    """
    Register a Plotly figure for inclusion in PDF export.
    
    Args:
        fig: Plotly figure object
        title: Figure title
        section: Section name (e.g., "Macro", "Benchmark")
    """
    if "figure_registry" not in st.session_state:
        st.session_state["figure_registry"] = []
    
    st.session_state["figure_registry"].append({
        "fig": fig,
        "title": title,
        "section": section,
        "timestamp": st.session_state.get("time_view", TIME_FULL)
    })


def clear_figure_registry() -> None:
    """Clear all registered figures (useful for page reloads)."""
    st.session_state["figure_registry"] = []


def get_figure_registry() -> List[Dict]:
    """Get all registered figures."""
    return st.session_state.get("figure_registry", [])


def figure_count() -> int:
    """Get count of registered figures."""
    return len(st.session_state.get("figure_registry", []))


# ==============================================================================
# ERROR HANDLING
# ==============================================================================

def set_last_error(msg: str) -> None:
    """Set last error message in session state."""
    st.session_state["last_error"] = msg


def get_last_error() -> str:
    """Get last error message."""
    return st.session_state.get("last_error", "")


def clear_last_error() -> None:
    """Clear error message."""
    st.session_state["last_error"] = ""


# ==============================================================================
# THEME HELPERS
# ==============================================================================

def inject_custom_css() -> None:
    """Inject custom CSS for styling."""
    base_css = """
    <style>
    /* Better spacing and max width handling */
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
    div[data-testid="stMetricValue"] { font-size: 1.55rem; }
    div[data-testid="stMetricDelta"] { font-size: 0.9rem; }
    /* Make dataframe more readable */
    .stDataFrame { border-radius: 8px; overflow: hidden; }
    /* Sidebar polish */
    section[data-testid="stSidebar"] { padding-top: 1rem; }
    /* Headings spacing */
    h1, h2, h3 { margin-top: 0.6rem; }
    /* Buttons */
    .stButton>button { border-radius: 10px; }
    </style>
    """
    st.markdown(base_css, unsafe_allow_html=True)
    
    # Optional forced theme
    if st.session_state["theme_mode"] == THEME_DARK_FORCE:
        dark_css = """
        <style>
        html, body, [data-testid="stAppViewContainer"] { background-color: #0e1117 !important; color: #e6e6e6 !important; }
        [data-testid="stSidebar"] { background-color: #0b0f14 !important; }
        .stMarkdown, .stText, .stCaption { color: #e6e6e6 !important; }
        </style>
        """
        st.markdown(dark_css, unsafe_allow_html=True)
    elif st.session_state["theme_mode"] == THEME_LIGHT_FORCE:
        light_css = """
        <style>
        html, body, [data-testid="stAppViewContainer"] { background-color: #ffffff !important; color: #111111 !important; }
        [data-testid="stSidebar"] { background-color: #f7f7f9 !important; }
        </style>
        """
        st.markdown(light_css, unsafe_allow_html=True)

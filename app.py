# -*- coding: utf-8 -*-
"""
EV Market Intelligence Suite | Streamlit App
Robust, production-ready single-file app (~500–1000 lines).

Notas de despliegue (Streamlit Cloud):
- Preferible incluir el parquet en el repo o definir una URL en st.secrets:
  DATA_URL = "https://.../historial_lite.parquet"
- También soporta carga manual por el usuario (file_uploader).
- Evita dependencias frágiles (p.ej. trendline OLS de Plotly) implementando regresión simple con NumPy.

Requisitos sugeridos (ajusta tu requirements.txt):
streamlit
pandas
plotly
pyarrow
fpdf
numpy
"""

from __future__ import annotations

import os
import io
import gc
import re
import math
import time
import json
import calendar
import traceback
from dataclasses import dataclass
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from fpdf import FPDF
from urllib.request import urlopen, Request


# ==============================================================================
# 0) PAGE CONFIG (must be first Streamlit command)
# ==============================================================================
st.set_page_config(
    page_title="EV Market Intelligence Suite | Enterprise",
    layout="wide",
    page_icon="🧠",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://www.streamlit.io",
        "Report a bug": "mailto:soporte@tuempresa.com",
        "About": "# Market Intelligence Suite\nHerramienta de análisis estratégico.",
    },
)

# ==============================================================================
# 1) CONSTANTS / CONFIG
# ==============================================================================
APP_VERSION = "v27.5 (robusto)"
DEFAULT_LOCAL_PARQUET = "historial_lite.parquet"

# Session state canonical keys/values
THEME_SYSTEM = "SYSTEM"
THEME_DARK_FORCE = "DARK_FORCE"
THEME_LIGHT_FORCE = "LIGHT_FORCE"

TIME_FULL = "FULL"
TIME_YTD = "YTD"

TIME_VIEW_LABELS = {
    "Full Year (Completo)": TIME_FULL,
    "YTD (Year to Date)": TIME_YTD,
}

# Column canonicalization
CANON_COLS = {
    "FECHA": "FECHA",
    "AÑO": "AÑO",
    "ANO": "AÑO",
    "ANIO": "AÑO",
    "MES": "MES",
    "MES_NUM": "MES_NUM",
    "MARCA": "MARCA",
    "MODELO": "MODELO",
    "EMPRESA": "EMPRESA",
    "COMBUSTIBLE": "COMBUSTIBLE",
    "CARROCERIA": "CARROCERIA",
    "CANTIDAD": "CANTIDAD",
    "VALOR US$ CIF": "VALOR US$ CIF",
    "VALOR USD CIF": "VALOR US$ CIF",
    "VALOR_USD_CIF": "VALOR US$ CIF",
    "CIF": "VALOR US$ CIF",
    "FLETE": "FLETE",
    "FLETE_USD": "FLETE",
}

TEXT_COLS = ["MARCA", "MODELO", "EMPRESA", "COMBUSTIBLE", "CARROCERIA", "MES"]
NUM_COLS = ["CANTIDAD", "VALOR US$ CIF", "FLETE"]

BRAND_FIXES = {
    "M.G.": "MG",
    "M. G.": "MG",
    "MORRIS GARAGES": "MG",
    "BYD AUTO": "BYD",
    "TOYOTA MOTOR": "TOYOTA",
    "MB": "MERCEDES-BENZ",
}

PRICE_BINS = [0, 15000, 25000, 40000, 70000, 1000000]
PRICE_LABELS = [
    "Económico (<15k)",
    "Masivo (15-25k)",
    "Medio (25-40k)",
    "Premium (40-70k)",
    "Lujo (>70k)",
]

# Business-safe ranges (avoid distorted plots by data errors)
CIF_MIN_VALID = 2000
CIF_MAX_VALID = 150000
FLETE_MIN_VALID = 50
FLETE_MAX_VALID = 8000


# ==============================================================================
# 2) STATE / UTILITIES
# ==============================================================================
def init_session_state() -> None:
    if "theme_mode" not in st.session_state:
        st.session_state["theme_mode"] = THEME_SYSTEM

    if "time_view" not in st.session_state:
        # CANONICAL value, not UI label (prevents rerun loops)
        st.session_state["time_view"] = TIME_FULL

    if "debug_mode" not in st.session_state:
        st.session_state["debug_mode"] = False

    if "data_source_mode" not in st.session_state:
        st.session_state["data_source_mode"] = "AUTO"  # AUTO | UPLOAD | LOCAL | URL

    if "data_url" not in st.session_state:
        # Optional: set via st.secrets["DATA_URL"]
        st.session_state["data_url"] = ""

    if "last_error" not in st.session_state:
        st.session_state["last_error"] = ""


def safe_upper_str(x) -> str:
    if x is None:
        return ""
    return str(x).strip().upper()


def to_number_series(s: pd.Series) -> pd.Series:
    # Robust numeric coercion: handles commas, currency symbols, whitespace.
    # Example: "$12,345.67" -> 12345.67
    s2 = s.astype(str).str.replace(r"[,$₡\s]", "", regex=True)
    s2 = s2.str.replace(r"(?<=\d)\.(?=\d{3}\b)", "", regex=True)  # remove thousands dots (EU)
    s2 = s2.str.replace(",", ".", regex=False)  # comma decimal
    return pd.to_numeric(s2, errors="coerce").fillna(0)


def month_abbr_es(m: int) -> str:
    # calendar.month_abbr is English; quick ES mapping
    es = {
        1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
    }
    return es.get(int(m), str(m))


def human_money(x: float) -> str:
    try:
        if abs(x) >= 1e9:
            return f"${x/1e9:,.2f} B"
        if abs(x) >= 1e6:
            return f"${x/1e6:,.2f} M"
        return f"${x:,.0f}"
    except Exception:
        return str(x)


def inject_custom_css() -> None:
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

    # Optional forced theme (CSS hack). Keep minimal to avoid breaking Streamlit updates.
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


def set_last_error(msg: str) -> None:
    st.session_state["last_error"] = msg


def render_debug_panel(df: Optional[pd.DataFrame], ultima_fecha: Optional[pd.Timestamp]) -> None:
    with st.expander("🧪 Diagnóstico (debug)", expanded=False):
        st.write("Versión:", APP_VERSION)
        st.write("time_view:", st.session_state.get("time_view"))
        st.write("theme_mode:", st.session_state.get("theme_mode"))
        if ultima_fecha is not None:
            st.write("Última fecha detectada:", str(ultima_fecha))
        if df is not None:
            st.write("Filas:", len(df), " | Columnas:", len(df.columns))
            st.write("Columnas:", list(df.columns))
        if st.session_state.get("last_error"):
            st.error(st.session_state["last_error"])
        if st.button("Limpiar cachés (cache_data)"):
            st.cache_data.clear()
            st.success("Cache limpiado. Recargando...")
            st.rerun()


# ==============================================================================
# 3) DATA LAYER (ETL) - robust
# ==============================================================================
def _download_bytes(url: str, timeout: int = 30) -> bytes:
    # Basic UA to avoid some blocks
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


@st.cache_data(show_spinner=False)
def load_parquet_from_url(url: str) -> pd.DataFrame:
    b = _download_bytes(url)
    bio = io.BytesIO(b)
    return pd.read_parquet(bio)


@st.cache_data(show_spinner=False)
def load_parquet_from_bytes(b: bytes) -> pd.DataFrame:
    return pd.read_parquet(io.BytesIO(b))


@st.cache_data(show_spinner=False)
def load_parquet_from_local(path: str) -> pd.DataFrame:
    return pd.read_parquet(path)


def canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # Normalize: strip, upper, collapse spaces
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.upper()
    )

    # Map aliases to canonical names
    new_cols = []
    for c in df.columns:
        c2 = CANON_COLS.get(c, c)
        new_cols.append(c2)
    df.columns = new_cols

    return df


def ensure_required_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    # Not all modules require all columns, but core columns should exist.
    required = ["CANTIDAD", "VALOR US$ CIF", "FECHA", "MARCA"]
    missing = [c for c in required if c not in df.columns]

    # If FECHA missing but AÑO + MES exist, try to build FECHA
    if "FECHA" in missing and ("AÑO" in df.columns) and ("MES_NUM" in df.columns):
        try:
            df = df.copy()
            df["FECHA"] = pd.to_datetime(
                df["AÑO"].astype(int).astype(str) + "-" + df["MES_NUM"].astype(int).astype(str) + "-01",
                errors="coerce",
            )
            missing = [c for c in required if c not in df.columns]
        except Exception:
            pass

    return df, missing


def etl_clean(df: pd.DataFrame) -> Tuple[pd.DataFrame, Optional[pd.Timestamp]]:
    df = canonicalize_columns(df)

    # Text columns
    for col in TEXT_COLS:
        if col in df.columns:
            df[col] = df[col].map(safe_upper_str)

    # Brand cleaning
    if "MARCA" in df.columns:
        df["MARCA"] = df["MARCA"].replace(BRAND_FIXES)

    # Numeric columns
    for col in NUM_COLS:
        if col in df.columns:
            df[col] = to_number_series(df[col])

    # Dates
    ultima_fecha = None
    if "FECHA" in df.columns:
        df["FECHA"] = pd.to_datetime(df["FECHA"], errors="coerce")
        df = df.dropna(subset=["FECHA"]).copy()
        df["AÑO"] = df["FECHA"].dt.year.astype(int)
        df["MES_NUM"] = df["FECHA"].dt.month.astype(int)
        ultima_fecha = df["FECHA"].max()

    # Derived KPIs
    if "VALOR US$ CIF" in df.columns and "CANTIDAD" in df.columns:
        denom = df["CANTIDAD"].replace(0, np.nan)
        df["CIF_UNITARIO"] = (df["VALOR US$ CIF"] / denom).replace([np.inf, -np.inf], np.nan).fillna(0)

    if "FLETE" in df.columns and "CANTIDAD" in df.columns:
        denom = df["CANTIDAD"].replace(0, np.nan)
        df["FLETE_UNITARIO"] = (df["FLETE"] / denom).replace([np.inf, -np.inf], np.nan).fillna(0)

    # Quality guardrails
    if "CANTIDAD" in df.columns:
        df = df[df["CANTIDAD"] >= 0].copy()

    return df, ultima_fecha


def apply_time_view(df: pd.DataFrame, ultima_fecha: Optional[pd.Timestamp]) -> pd.DataFrame:
    if st.session_state["time_view"] == TIME_YTD and ultima_fecha is not None:
        mes_corte = int(ultima_fecha.month)
        if "MES_NUM" in df.columns:
            return df[df["MES_NUM"] <= mes_corte].copy()
    return df


def get_data_source_status(local_exists: bool, url_exists: bool) -> str:
    if local_exists and url_exists:
        return "LOCAL/URL disponibles"
    if local_exists:
        return "LOCAL disponible"
    if url_exists:
        return "URL disponible"
    return "Sin fuente automática"


def load_data_flow() -> Tuple[Optional[pd.DataFrame], Optional[pd.Timestamp], str]:
    """
    Unified data flow:
    1) If user uploaded: use it.
    2) Else if local parquet exists: use it.
    3) Else if secrets/url set: download and use it.
    4) Else return None.
    """
    # A) Uploaded file (preferred if local missing)
    uploaded = st.session_state.get("uploaded_parquet")
    if uploaded is not None:
        try:
            df0 = load_parquet_from_bytes(uploaded)
            df, ultima = etl_clean(df0)
            return df, ultima, "UPLOAD"
        except Exception as e:
            set_last_error(f"Error leyendo parquet cargado: {e}")
            return None, None, "UPLOAD_ERROR"

    # B) Local file
    local_path = os.getenv("DATA_PATH", DEFAULT_LOCAL_PARQUET)
    if os.path.exists(local_path):
        try:
            df0 = load_parquet_from_local(local_path)
            df, ultima = etl_clean(df0)
            return df, ultima, "LOCAL"
        except Exception as e:
            set_last_error(f"Error leyendo parquet local ({local_path}): {e}")
            return None, None, "LOCAL_ERROR"

    # C) URL (secrets or session)
    url = ""
    try:
        url = st.secrets.get("DATA_URL", "")  # optional
    except Exception:
        url = ""
    if not url:
        url = st.session_state.get("data_url", "")

    if url:
        try:
            df0 = load_parquet_from_url(url)
            df, ultima = etl_clean(df0)
            return df, ultima, "URL"
        except Exception as e:
            set_last_error(f"Error descargando/leyendo parquet URL: {e}")
            return None, None, "URL_ERROR"

    # D) No data
    return None, None, "NO_DATA"


# ==============================================================================
# 4) PDF REPORTING (FPDF) - robust encoding
# ==============================================================================
class ExecutivePDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(30, 55, 153)
        self.cell(0, 8, "Reporte de Inteligencia de Mercado - Automotriz", 0, 1, "C")
        self.ln(2)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120)
        fecha_gen = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.cell(0, 10, f"Pag {self.page_no()} | Generado {fecha_gen} | Confidencial", 0, 0, "C")


def pdf_sanitize(text) -> str:
    # FPDF classic expects latin-1, so we replace unsupported chars.
    try:
        return str(text).encode("latin-1", "replace").decode("latin-1")
    except Exception:
        return str(text)


@st.cache_data(show_spinner=False)
def build_pdf_bytes(df_dict: Dict[str, List], title: str, subtitle: str, view_mode: str) -> bytes:
    df = pd.DataFrame(df_dict)

    pdf = ExecutivePDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()

    # Title block
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(0)
    pdf.cell(0, 10, pdf_sanitize(title), 0, 1, "L")
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(90)
    pdf.cell(0, 7, pdf_sanitize(f"Vista Temporal: {view_mode} | {subtitle}"), 0, 1, "L")
    pdf.ln(3)

    # Executive KPIs box
    total_vol = float(df["CANTIDAD"].sum()) if "CANTIDAD" in df.columns else 0.0
    total_val = float(df["VALOR US$ CIF"].sum()) if "VALOR US$ CIF" in df.columns else 0.0
    ticket = (total_val / total_vol) if total_vol else 0.0

    pdf.set_fill_color(245, 245, 245)
    pdf.set_draw_color(220, 220, 220)
    pdf.rect(10, 40, 190, 20, "FD")

    pdf.set_y(45)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(0)
    pdf.cell(63, 8, pdf_sanitize(f"Volumen: {total_vol:,.0f}"), 0, 0, "C")
    pdf.cell(63, 8, pdf_sanitize(f"Inversión: {human_money(total_val)}"), 0, 0, "C")
    pdf.cell(63, 8, pdf_sanitize(f"Ticket: {human_money(ticket)}"), 0, 1, "C")
    pdf.ln(10)

    # Main ranking
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 55, 153)

    if "MODELO" in df.columns and df["MODELO"].nunique() > 1:
        group = "MODELO"
    elif "MARCA" in df.columns:
        group = "MARCA"
    else:
        group = "AÑO" if "AÑO" in df.columns else None

    if group is not None and group in df.columns and "CANTIDAD" in df.columns:
        pdf.cell(0, 8, pdf_sanitize(f"Top 15 por {group}"), 0, 1, "L")
        pdf.ln(1)

        top = df.groupby(group)["CANTIDAD"].sum().sort_values(ascending=False).head(15)

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(255)
        pdf.set_fill_color(44, 62, 80)
        pdf.cell(140, 7, pdf_sanitize(group), 1, 0, "L", 1)
        pdf.cell(50, 7, "Unidades", 1, 1, "R", 1)

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(0)
        alt = False
        for name, val in top.items():
            pdf.set_fill_color(240, 240, 240) if alt else pdf.set_fill_color(255, 255, 255)
            pdf.cell(140, 7, pdf_sanitize(str(name))[:65], 1, 0, "L", alt)
            pdf.cell(50, 7, pdf_sanitize(f"{val:,.0f}"), 1, 1, "R", alt)
            alt = not alt
    else:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0)
        pdf.multi_cell(0, 6, pdf_sanitize("No hay columnas suficientes para construir un ranking (se requieren CANTIDAD y una dimensión)."))

    # Importers block
    if "EMPRESA" in df.columns and "CANTIDAD" in df.columns:
        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(30, 55, 153)
        pdf.cell(0, 8, "Top 5 Importadores", 0, 1, "L")
        top_imp = df.groupby("EMPRESA")["CANTIDAD"].sum().sort_values(ascending=False).head(5)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0)
        for name, val in top_imp.items():
            pdf.cell(140, 6, pdf_sanitize(f"- {name}")[:80], 0, 0, "L")
            pdf.cell(50, 6, pdf_sanitize(f"{val:,.0f}"), 0, 1, "R")

    return pdf.output(dest="S").encode("latin-1")


# ==============================================================================
# 5) ANALYTICS HELPERS (groupbys, yoy, regression)
# ==============================================================================
@st.cache_data(show_spinner=False)
def agg_monthly(df: pd.DataFrame) -> pd.DataFrame:
    m = df.groupby(["AÑO", "MES_NUM"])["CANTIDAD"].sum().reset_index()
    m["Fecha"] = pd.to_datetime(m["AÑO"].astype(str) + "-" + m["MES_NUM"].astype(str) + "-01", errors="coerce")
    return m.dropna(subset=["Fecha"])


@st.cache_data(show_spinner=False)
def top_share(df: pd.DataFrame, dim: str, top_n: int = 15) -> pd.DataFrame:
    t = df.groupby(dim)["CANTIDAD"].sum().sort_values(ascending=False).head(top_n).reset_index()
    denom = t["CANTIDAD"].sum()
    t["Share"] = (t["CANTIDAD"] / denom * 100) if denom else 0
    return t


def linear_regression_forecast(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """
    Returns (slope, intercept) of y = m*x + b using np.polyfit.
    x should be numeric (e.g., 1..12).
    """
    if len(x) < 2 or np.all(y == y[0]):
        return 0.0, float(y.mean()) if len(y) else 0.0
    m, b = np.polyfit(x, y, 1)
    return float(m), float(b)


def yoy_table(df_main: pd.DataFrame, df_view: pd.DataFrame, dim_col: str, sel_years: List[int]) -> Optional[pd.DataFrame]:
    if len(sel_years) < 2:
        return None

    curr_y = int(max(sel_years))
    prev_y = int(curr_y - 1)

    df_curr = df_view[df_view["AÑO"] == curr_y]
    df_prev = df_main[df_main["AÑO"] == prev_y]

    if df_curr.empty and df_prev.empty:
        return None

    grp_curr = df_curr.groupby(dim_col).agg(
        Vol_Actual=("CANTIDAD", "sum"),
        CIF_Actual=("VALOR US$ CIF", "sum"),
    ).reset_index()

    grp_prev = df_prev.groupby(dim_col).agg(
        Vol_Prev=("CANTIDAD", "sum"),
        CIF_Prev=("VALOR US$ CIF", "sum"),
    ).reset_index()

    if grp_curr["Vol_Actual"].sum() > 0:
        grp_curr["Share_Actual"] = grp_curr["Vol_Actual"] / grp_curr["Vol_Actual"].sum() * 100
    else:
        grp_curr["Share_Actual"] = 0

    if grp_prev["Vol_Prev"].sum() > 0:
        grp_prev["Share_Prev"] = grp_prev["Vol_Prev"] / grp_prev["Vol_Prev"].sum() * 100
    else:
        grp_prev["Share_Prev"] = 0

    out = pd.merge(grp_curr, grp_prev, on=dim_col, how="outer").fillna(0)
    out["Δ Share (pp)"] = out["Share_Actual"] - out["Share_Prev"]
    out["Δ Inversión ($)"] = out["CIF_Actual"] - out["CIF_Prev"]
    out["Estado"] = np.where(out["Δ Share (pp)"] >= 0, "🟢 Ganó", "🔻 Perdió")
    return out


# ==============================================================================
# 6) UI COMPONENTS
# ==============================================================================
def sidebar_controls(df_raw: Optional[pd.DataFrame], ultima_fecha: Optional[pd.Timestamp], source_mode: str) -> None:
    with st.sidebar:
        st.title("🧠 Market Suite")
        st.caption(f"{APP_VERSION} | Enterprise Edition")

        # Debug
        st.session_state["debug_mode"] = st.toggle("Modo debug", value=st.session_state["debug_mode"])

        st.divider()
        st.subheader("📦 Datos")

        # Offer upload always (useful if deploy lacks parquet)
        up = st.file_uploader("Cargar historial_lite.parquet", type=["parquet"])
        if up is not None:
            st.session_state["uploaded_parquet"] = up.getvalue()
            st.success("Parquet cargado. Recargando…")
            st.rerun()

        # URL input (optional)
        st.session_state["data_url"] = st.text_input(
            "DATA_URL (opcional)",
            value=st.session_state.get("data_url", ""),
            help="Si no hay archivo local, se intentará descargar el parquet desde esta URL.",
        )

        local_path = os.getenv("DATA_PATH", DEFAULT_LOCAL_PARQUET)
        local_exists = os.path.exists(local_path)
        url_exists = bool(st.secrets.get("DATA_URL", "") if hasattr(st, "secrets") else "") or bool(st.session_state.get("data_url"))

        st.caption(f"Fuente detectada: {source_mode} | {get_data_source_status(local_exists, url_exists)}")
        if df_raw is not None:
            st.success("✅ Datos cargados")
            if ultima_fecha is not None:
                st.info(f"📅 Data actualizada al: {ultima_fecha.strftime('%d-%b-%Y')}")
        else:
            st.error("⚠️ No hay datos disponibles (local/url/upload).")

        st.divider()
        st.subheader("⚙️ Preferencias")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🌙 Dark", use_container_width=True):
                st.session_state["theme_mode"] = THEME_DARK_FORCE
                st.rerun()
        with c2:
            if st.button("☀️ Light", use_container_width=True):
                st.session_state["theme_mode"] = THEME_LIGHT_FORCE
                st.rerun()

        # Time view (robust)
        labels = list(TIME_VIEW_LABELS.keys())
        current_label = next(k for k, v in TIME_VIEW_LABELS.items() if v == st.session_state["time_view"])
        current_index = labels.index(current_label)

        st.markdown("**Visión Temporal:**")
        time_label = st.radio(
            "Corte de Datos:",
            labels,
            index=current_index,
            label_visibility="collapsed",
        )
        new_value = TIME_VIEW_LABELS[time_label]
        if new_value != st.session_state["time_view"]:
            st.session_state["time_view"] = new_value
            st.rerun()

        st.divider()
        st.subheader("📍 Módulos")
        menu = st.radio(
            "Ir a:",
            ["🌍 1. Visión País (Macro)", "⚔️ 2. Guerra de Marcas (Benchmark)", "🔍 3. Auditoría de Marca (Deep Dive)"],
            label_visibility="collapsed",
        )
        st.session_state["menu"] = menu


def kpi_row(kpis: List[Tuple[str, str, str]]) -> None:
    cols = st.columns(len(kpis))
    for c, (label, value, delta) in zip(cols, kpis):
        c.metric(label, value, delta=delta)


# ==============================================================================
# 7) PAGES / MODULES
# ==============================================================================
def page_macro(df_main: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    st.title(f"🌍 Visión País: {TIME_FULL if st.session_state['time_view']==TIME_FULL else 'YTD'}")
    st.caption("Análisis macro de importaciones automotrices.")

    years_avail = sorted(df_main["AÑO"].unique(), reverse=True)
    default_years = years_avail[:2] if len(years_avail) >= 2 else years_avail
    sel_years = st.multiselect("Periodo de Análisis", years_avail, default=default_years)

    if not sel_years:
        st.warning("Selecciona al menos un año.")
        return df_main.iloc[0:0].copy(), "Reporte Macro País"

    df_view = df_main[df_main["AÑO"].isin(sel_years)].copy()
    vol = float(df_view["CANTIDAD"].sum())
    val = float(df_view["VALOR US$ CIF"].sum())
    tkt = (val / vol) if vol else 0.0

    kpi_row([
        ("Volumen Total", f"{vol:,.0f}", "Unidades"),
        ("Inversión CIF", human_money(val), "USD"),
        ("Ticket Promedio", human_money(tkt), "CIF unitario"),
        ("Marcas Activas", f"{df_view['MARCA'].nunique():,}", "Competidores"),
    ])

    st.markdown("---")
    col_a, col_b = st.columns([2, 1])

    with col_a:
        st.subheader("📈 Ritmo de Importación (Serie de tiempo)")
        monthly = agg_monthly(df_view)
        if monthly.empty:
            st.info("Sin datos mensuales suficientes.")
        else:
            fig = px.line(
                monthly,
                x="Fecha",
                y="CANTIDAD",
                markers=True,
                color="AÑO",
                labels={"CANTIDAD": "Unidades", "Fecha": "Mes"},
            )
            fig.update_layout(xaxis_title=None, legend_title="Año")
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("⚡ Mix Energético")
        if "COMBUSTIBLE" in df_view.columns and df_view["COMBUSTIBLE"].nunique() > 0:
            fig = px.pie(
                df_view,
                values="CANTIDAD",
                names="COMBUSTIBLE",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Prism,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay columna COMBUSTIBLE o está vacía.")

    col_c, col_d = st.columns(2)

    with col_c:
        st.subheader("💰 Segmentación de Precios")
        if "CIF_UNITARIO" not in df_view.columns:
            st.info("No se pudo calcular CIF_UNITARIO.")
        else:
            df_seg = df_view.copy()
            df_seg["SEGMENTO"] = pd.cut(df_seg["CIF_UNITARIO"], bins=PRICE_BINS, labels=PRICE_LABELS)
            seg = df_seg.groupby("SEGMENTO", observed=True)["CANTIDAD"].sum().reset_index()
            if seg.empty:
                st.info("Sin datos para segmentación.")
            else:
                fig = px.bar(seg, x="CANTIDAD", y="SEGMENTO", orientation="h", color="SEGMENTO", text_auto=True)
                fig.update_layout(showlegend=False, xaxis_title="Unidades", yaxis_title=None)
                st.plotly_chart(fig, use_container_width=True)

    with col_d:
        st.subheader("🏆 Market Share (Top 15)")
        top = top_share(df_view, dim="MARCA", top_n=15)
        if top.empty:
            st.info("Sin datos para ranking.")
        else:
            st.dataframe(
                top,
                column_config={
                    "CANTIDAD": st.column_config.ProgressColumn("Volumen", format="%d", min_value=0, max_value=int(top["CANTIDAD"].max() or 1)),
                    "Share": st.column_config.NumberColumn("Part. %", format="%.1f%%"),
                },
                hide_index=True,
                use_container_width=True,
            )

    st.markdown("---")
    st.subheader("📊 Crecimiento Anual (YoY)")
    st.caption("Compara el año máximo seleccionado vs el año anterior (n-1).")

    dim_col = st.radio("Dimensión:", ["MARCA", "MODELO", "COMBUSTIBLE", "CARROCERIA"], horizontal=True)
    if dim_col not in df_main.columns:
        st.warning(f"No existe la columna {dim_col}.")
    else:
        df_yoy = yoy_table(df_main, df_view, dim_col, sel_years)
        if df_yoy is None:
            st.warning("Selecciona al menos 2 años para habilitar el YoY.")
        else:
            df_show = df_yoy.sort_values("Vol_Actual", ascending=False).head(50)
            st.dataframe(
                df_show,
                column_config={
                    dim_col: st.column_config.TextColumn("Categoría"),
                    "Vol_Actual": st.column_config.NumberColumn("Vol (Actual)", format="%d"),
                    "Vol_Prev": st.column_config.NumberColumn("Vol (Prev)", format="%d"),
                    "Share_Actual": st.column_config.ProgressColumn("Share Actual", format="%.1f%%", min_value=0, max_value=30),
                    "Δ Share (pp)": st.column_config.NumberColumn("Var Share", format="%+.1f pp"),
                    "Δ Inversión ($)": st.column_config.NumberColumn("Var Inversión", format="$%d"),
                    "Estado": st.column_config.TextColumn("Tendencia"),
                },
                hide_index=True,
                use_container_width=True,
            )

    # Export dataset and title
    return df_view, "Reporte Macro País"


def page_benchmark(df_main: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    st.title(f"⚔️ Benchmarking Competitivo: {TIME_FULL if st.session_state['time_view']==TIME_FULL else 'YTD'}")
    st.caption("Comparación de rivales (volumen, mix, precios, canal oficial vs gris).")

    years_avail = sorted(df_main["AÑO"].unique(), reverse=True)
    sel_years = st.multiselect("Años a comparar", years_avail, default=years_avail[:1] if years_avail else [])

    if not sel_years:
        st.warning("Selecciona al menos un año.")
        return df_main.iloc[0:0].copy(), "Reporte Competitivo"

    df_curr = df_main[df_main["AÑO"].isin(sel_years)].copy()
    all_brands = sorted(df_curr["MARCA"].dropna().unique())

    c0, c1 = st.columns([1, 2])
    with c0:
        select_all = st.checkbox("Seleccionar todas", value=False)
    with c1:
        default_top = df_curr["MARCA"].value_counts().head(3).index.tolist()
        sel_brands = all_brands if select_all else st.multiselect("Marcas", all_brands, default=default_top)

    if not sel_brands:
        st.warning("Selecciona al menos una marca.")
        return df_curr.iloc[0:0].copy(), "Reporte Competitivo"

    df_view = df_curr[df_curr["MARCA"].isin(sel_brands)].copy()
    if df_view.empty:
        st.info("No hay datos para la selección.")
        return df_view, "Reporte Competitivo"

    t1, t2, t3 = st.tabs(["📊 Volumen & Mix", "💰 Precios", "🕵️ Auditoría Gris"])

    with t1:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Batalla de Volumen")
            fig = px.bar(df_view, x="MARCA", y="CANTIDAD", color="AÑO", barmode="group")
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader("Estrategia de Motorización (Mix)")
            if "COMBUSTIBLE" in df_view.columns:
                fig = px.bar(df_view, x="MARCA", y="CANTIDAD", color="COMBUSTIBLE", barmode="stack")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No existe columna COMBUSTIBLE.")

    with t2:
        st.subheader("Matriz de Precios (CIF Unitario)")
        if "CIF_UNITARIO" not in df_view.columns:
            st.info("No se pudo calcular CIF_UNITARIO.")
        else:
            df_p = df_view[(df_view["CIF_UNITARIO"] > CIF_MIN_VALID) & (df_view["CIF_UNITARIO"] < CIF_MAX_VALID)].copy()
            if df_p.empty:
                st.info("Sin datos válidos de precios en el rango.")
            else:
                fig = px.box(df_p, x="MARCA", y="CIF_UNITARIO", color="MARCA", points="outliers")
                fig.update_layout(showlegend=False, yaxis_title="CIF unitario")
                st.plotly_chart(fig, use_container_width=True)
                st.caption("Cajas alargadas = portafolio amplio; cajas pequeñas = nicho o consistencia de precios.")

    with t3:
        st.subheader("Auditoría de Fuga (Oficial vs Paralelo)")
        if "EMPRESA" not in df_view.columns:
            st.info("No existe columna EMPRESA.")
        else:
            gb = df_view.groupby(["MARCA", "EMPRESA"])["CANTIDAD"].sum().reset_index()
            lideres = gb.sort_values(["MARCA", "CANTIDAD"], ascending=[True, False]).drop_duplicates("MARCA")
            lideres = lideres.rename(columns={"EMPRESA": "LIDER_OFICIAL"})[["MARCA", "LIDER_OFICIAL"]]
            df_x = df_view.merge(lideres, on="MARCA", how="left")
            df_x["CANAL"] = np.where(df_x["EMPRESA"] == df_x["LIDER_OFICIAL"], "OFICIAL", "GRIS")

            c_g1, c_g2 = st.columns(2)
            with c_g1:
                resumen = df_x.groupby(["MARCA", "CANAL"])["CANTIDAD"].sum().unstack().fillna(0).reset_index()
                cols = [c for c in ["OFICIAL", "GRIS"] if c in resumen.columns]
                fig = px.bar(
                    resumen,
                    x="MARCA",
                    y=cols,
                    barmode="stack",
                    title="Volumen por Canal",
                    color_discrete_map={"OFICIAL": "#27ae60", "GRIS": "#95a5a6"},
                )
                st.plotly_chart(fig, use_container_width=True)

            with c_g2:
                if "GRIS" in resumen.columns and "OFICIAL" in resumen.columns:
                    resumen["Total"] = resumen["OFICIAL"] + resumen["GRIS"]
                    resumen["% Fuga"] = np.where(resumen["Total"] > 0, resumen["GRIS"] / resumen["Total"] * 100, 0)
                    fig = px.bar(
                        resumen.sort_values("% Fuga", ascending=False),
                        x="MARCA",
                        y="% Fuga",
                        title="Ranking Vulnerabilidad (% Fuga)",
                        text_auto=".1f",
                        color="% Fuga",
                        color_continuous_scale="Reds",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.success("No se detectó fuga relevante en las marcas seleccionadas.")

            st.markdown("**Distribuidor oficial detectado (heurística: mayor importador por marca):**")
            st.dataframe(lideres.set_index("MARCA"), use_container_width=True)

    return df_view, "Reporte Competitivo"


def page_deep_dive(df_main: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    st.title(f"🔍 Auditoría Profunda: {TIME_FULL if st.session_state['time_view']==TIME_FULL else 'YTD'}")
    st.caption("Análisis a nivel marca: Pareto, tendencia, logística y estacionalidad.")

    years_avail = sorted(df_main["AÑO"].unique(), reverse=True)
    if not years_avail:
        st.warning("No hay años disponibles.")
        return df_main.iloc[0:0].copy(), "Auditoría"

    y = st.selectbox("Año fiscal", years_avail)
    df_y = df_main[df_main["AÑO"] == y].copy()

    brands = sorted(df_y["MARCA"].dropna().unique())
    if not brands:
        st.warning("No hay marcas en el año seleccionado.")
        return df_y.iloc[0:0].copy(), "Auditoría"

    brand = st.selectbox("Marca a auditar", brands)
    df_view = df_y[df_y["MARCA"] == brand].copy()

    if df_view.empty:
        st.info("No hay datos para la marca/año seleccionados.")
        return df_view, f"Auditoría {brand} ({y})"

    vol = float(df_view["CANTIDAD"].sum())
    cif_avg = float(df_view["CIF_UNITARIO"].mean()) if "CIF_UNITARIO" in df_view.columns else 0.0
    flete_avg = float(df_view["FLETE_UNITARIO"].mean()) if "FLETE_UNITARIO" in df_view.columns else 0.0
    modelos = int(df_view["MODELO"].nunique()) if "MODELO" in df_view.columns else 0

    kpi_row([
        ("Volumen", f"{vol:,.0f}", ""),
        ("CIF Promedio", human_money(cif_avg), ""),
        ("Flete Promedio", human_money(flete_avg), ""),
        ("Modelos Activos", f"{modelos:,}", ""),
    ])

    tab_a, tab_b, tab_c = st.tabs(["📌 Eficiencia (Pareto)", "📈 Futuro (Tendencia)", "🚚 Logística"])

    with tab_a:
        st.subheader("Eficiencia de Portafolio (Pareto)")
        if "MODELO" not in df_view.columns:
            st.info("No existe columna MODELO.")
        else:
            pareto = df_view.groupby("MODELO")["CANTIDAD"].sum().sort_values(ascending=False).reset_index()
            total = pareto["CANTIDAD"].sum()
            pareto["% Acum"] = (pareto["CANTIDAD"].cumsum() / total * 100) if total else 0
            pareto["Clasificación"] = np.where(pareto["% Acum"] <= 80, "A (Vital)", "B (Cola)")
            fig = px.bar(
                pareto.head(40),
                x="MODELO",
                y="CANTIDAD",
                color="Clasificación",
                color_discrete_map={"A (Vital)": "#27ae60", "B (Cola)": "#95a5a6"},
            )
            fig.update_layout(xaxis_title=None)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(pareto.head(50), hide_index=True, use_container_width=True)

    with tab_b:
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("Proyección de Tendencia (regresión simple)")
            mensual = df_view.groupby("MES_NUM")["CANTIDAD"].sum().reset_index().sort_values("MES_NUM")
            if mensual.empty:
                st.info("Sin datos mensuales.")
            else:
                x = mensual["MES_NUM"].to_numpy(dtype=float)
                yv = mensual["CANTIDAD"].to_numpy(dtype=float)
                m, b = linear_regression_forecast(x, yv)
                mensual["Pred"] = m * mensual["MES_NUM"] + b
                mensual["Mes"] = mensual["MES_NUM"].apply(month_abbr_es)

                fig = go.Figure()
                fig.add_trace(go.Scatter(x=mensual["Mes"], y=mensual["CANTIDAD"], mode="lines+markers", name="Real"))
                fig.add_trace(go.Scatter(x=mensual["Mes"], y=mensual["Pred"], mode="lines", name="Tendencia", line=dict(color="red")))
                fig.update_layout(yaxis_title="Unidades", xaxis_title=None)
                st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.subheader("Evolución de Precio (Ticket)")
            if "CIF_UNITARIO" not in df_view.columns:
                st.info("No se pudo calcular CIF_UNITARIO.")
            else:
                evo = df_view.groupby("MES_NUM")["CIF_UNITARIO"].mean().reset_index().sort_values("MES_NUM")
                evo["Mes"] = evo["MES_NUM"].apply(month_abbr_es)
                fig = px.line(evo, x="Mes", y="CIF_UNITARIO", markers=True, labels={"CIF_UNITARIO": "CIF unitario"})
                st.plotly_chart(fig, use_container_width=True)

    with tab_c:
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("Costos Logísticos (Flete unitario)")
            if "FLETE_UNITARIO" not in df_view.columns:
                st.info("No se pudo calcular FLETE_UNITARIO.")
            else:
                fletes = df_view[(df_view["FLETE_UNITARIO"] > FLETE_MIN_VALID) & (df_view["FLETE_UNITARIO"] < FLETE_MAX_VALID)].copy()
                if fletes.empty:
                    st.info("Sin datos de fletes válidos en el rango.")
                else:
                    fig = px.box(fletes, y="FLETE_UNITARIO", points="outliers", title="Dispersión Flete Unitario")
                    fig.update_layout(yaxis_title="USD por unidad")
                    st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.subheader("Mapa de Calor Estacional (intensidad)")
            heat = df_view.groupby("MES_NUM")["CANTIDAD"].sum().reset_index().sort_values("MES_NUM")
            if heat.empty:
                st.info("Sin datos mensuales.")
            else:
                heat["Mes"] = heat["MES_NUM"].apply(month_abbr_es)
                # Heatmap simple (mes vs valor). Para 1D, lo renderizamos como barra de calor.
                fig = px.density_heatmap(
                    heat,
                    x="Mes",
                    y="CANTIDAD",
                    nbinsx=12,
                    title="Intensidad de Importación por Mes",
                    color_continuous_scale="Blues",
                )
                st.plotly_chart(fig, use_container_width=True)

    return df_view, f"Auditoría {brand} ({y})"


# ==============================================================================
# 8) EXPORTS / DOWNLOADS
# ==============================================================================
def sidebar_exports(df: pd.DataFrame, pdf_title: str) -> None:
    with st.sidebar:
        st.divider()
        st.markdown("### 📤 Exportar")

        # CSV download (filtered)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar CSV (filtrado)",
            data=csv,
            file_name=f"data_{pdf_title.replace(' ', '_')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

        # PDF
        try:
            data_dict = df.to_dict(orient="list")
            view_label = "Full Year" if st.session_state["time_view"] == TIME_FULL else "YTD"
            pdf_bytes = build_pdf_bytes(
                data_dict,
                pdf_title,
                subtitle=f"Modo: {view_label}",
                view_mode=view_label,
            )
            st.download_button(
                "📄 Descargar PDF Ejecutivo",
                data=pdf_bytes,
                file_name=f"Reporte_{pdf_title.replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.warning(f"Error generando PDF: {e}")


# ==============================================================================
# 9) MAIN APP
# ==============================================================================
def main() -> None:
    init_session_state()
    inject_custom_css()

    # Load data (with fallback)
    df_raw, ultima_fecha, source_mode = load_data_flow()

    sidebar_controls(df_raw, ultima_fecha, source_mode)

    if st.session_state.get("debug_mode"):
        render_debug_panel(df_raw, ultima_fecha)

    if df_raw is None:
        st.title("📉 Dashboard Autos CR")
        st.error("No hay datos cargados. Sube un parquet en el sidebar o configura DATA_URL / DATA_PATH.")
        st.stop()

    # Validate required columns; show readable error if missing
    df_raw, missing = ensure_required_columns(df_raw)
    if missing:
        st.title("📉 Dashboard Autos CR")
        st.error(f"Faltan columnas requeridas: {missing}")
        st.info("Solución: revisar el parquet o mapear nombres de columnas en CANON_COLS.")
        if st.session_state.get("debug_mode"):
            st.write("Columnas detectadas:", list(df_raw.columns))
        st.stop()

    # Apply time view
    df_main = apply_time_view(df_raw, ultima_fecha)

    # Route to module
    menu = st.session_state.get("menu", "🌍 1. Visión País (Macro)")

    pdf_dataset = df_main.iloc[0:0].copy()
    pdf_title = "Reporte"

    if menu == "🌍 1. Visión País (Macro)":
        pdf_dataset, pdf_title = page_macro(df_main)
    elif menu == "⚔️ 2. Guerra de Marcas (Benchmark)":
        pdf_dataset, pdf_title = page_benchmark(df_main)
    elif menu == "🔍 3. Auditoría de Marca (Deep Dive)":
        pdf_dataset, pdf_title = page_deep_dive(df_main)
    else:
        st.warning("Módulo no reconocido.")

    # Exports
    if pdf_dataset is not None and not pdf_dataset.empty:
        sidebar_exports(pdf_dataset, pdf_title)

    # Memory cleanup
    gc.collect()


# Entrypoint
if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        # Hard-fail safety
        set_last_error(str(ex))
        st.error("Error inesperado en la app. Activa 'Modo debug' para ver detalles.")
        with st.expander("Detalles técnicos", expanded=False):
            st.code(traceback.format_exc())

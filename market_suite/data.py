# -*- coding: utf-8 -*-
"""
Market Suite | Data Layer (ETL)

Extracts and manages data loading, cleaning, and transformation.
Previously in: app.py (monolithic)
"""

from __future__ import annotations
import os
import io
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from urllib.request import urlopen, Request
import streamlit as st

# ==============================================================================
# CONFIGURATION
# ==============================================================================

DEFAULT_LOCAL_PARQUET = "historial_lite.parquet"

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

# ==============================================================================
# UTILITIES
# ==============================================================================

def safe_upper_str(x) -> str:
    if x is None:
        return ""
    return str(x).strip().upper()


def to_number_series(s: pd.Series) -> pd.Series:
    """Robust numeric coercion: handles commas, currency symbols, whitespace."""
    s2 = s.astype(str).str.replace(r"[,$₡\s]", "", regex=True)
    s2 = s2.str.replace(r"(?<=\d)\.(?=\d{3}\b)", "", regex=True)
    s2 = s2.str.replace(",", ".", regex=False)
    return pd.to_numeric(s2, errors="coerce").fillna(0)


# ==============================================================================
# DATA LOADERS (cached)
# ==============================================================================

def _download_bytes(url: str, timeout: int = 30) -> bytes:
    """Download file from URL with basic UA."""
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


# ==============================================================================
# ETL FUNCTIONS
# ==============================================================================

def canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names: strip, upper, collapse spaces, apply aliases."""
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.upper()
    )
    
    new_cols = []
    for c in df.columns:
        c2 = CANON_COLS.get(c, c)
        new_cols.append(c2)
    df.columns = new_cols
    return df


def ensure_required_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Validate required columns exist. Build FECHA if needed."""
    required = ["CANTIDAD", "VALOR US$ CIF", "FECHA", "MARCA"]
    missing = [c for c in required if c not in df.columns]
    
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
    """Main ETL pipeline: canonicalize, clean, enrich."""
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
    
    # Dates and derived columns
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


def apply_time_view(df: pd.DataFrame, ultima_fecha: Optional[pd.Timestamp], time_view: str = "FULL") -> pd.DataFrame:
    """Apply temporal filtering (YTD vs Full year)."""
    if time_view == "YTD" and ultima_fecha is not None:
        mes_corte = int(ultima_fecha.month)
        if "MES_NUM" in df.columns:
            return df[df["MES_NUM"] <= mes_corte].copy()
    return df


def load_data_flow() -> Tuple[Optional[pd.DataFrame], Optional[pd.Timestamp], str]:
    """
    Unified data flow:
    1) If user uploaded: use it.
    2) Else if local parquet exists: use it.
    3) Else if secrets/url set: download and use it.
    4) Else return None.
    """
    # A) Uploaded file
    uploaded = st.session_state.get("uploaded_parquet")
    if uploaded is not None:
        try:
            df0 = load_parquet_from_bytes(uploaded)
            df, ultima = etl_clean(df0)
            return df, ultima, "UPLOAD"
        except Exception as e:
            st.session_state["last_error"] = f"Error leyendo parquet cargado: {e}"
            return None, None, "UPLOAD_ERROR"
    
    # B) Local file
    local_path = os.getenv("DATA_PATH", DEFAULT_LOCAL_PARQUET)
    if os.path.exists(local_path):
        try:
            df0 = load_parquet_from_local(local_path)
            df, ultima = etl_clean(df0)
            return df, ultima, "LOCAL"
        except Exception as e:
            st.session_state["last_error"] = f"Error leyendo parquet local ({local_path}): {e}"
            return None, None, "LOCAL_ERROR"
    
    # C) URL (secrets or session)
    url = ""
    try:
        url = st.secrets.get("DATA_URL", "")
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
            st.session_state["last_error"] = f"Error descargando/leyendo parquet URL: {e}"
            return None, None, "URL_ERROR"
    
    # D) No data
    return None, None, "NO_DATA"

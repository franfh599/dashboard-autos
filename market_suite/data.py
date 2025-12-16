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

# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_LOCAL_PARQUET = "historial_lite.parquet"

# Column canonicalization
CANON_COLS = {
    "FECHA": "fecha",
    "AÑO": "año",
    "ANO": "año",
    "ANIO": "año",
    "HES": "hes",
    "HES_NUM": "hes_num",
    "MARCA": "marca",
    "MARCA_GENERICA": "marca_generica",
    "MODELO": "modelo",
    "PRECIO_VENTA": "precio",
    "PRECIO": "precio",
    "PRECIO_LISTA": "precio_lista",
}

# =============================================================================
# DATA LOADING
# =============================================================================

@st.cache_data(ttl=3600)
def load_data_flow() -> pd.DataFrame | None:
    """
    Load data from local parquet file.
    Cached for 1 hour to improve performance.
    
    Returns:
        pd.DataFrame: Loaded and normalized data, or None if error
    """
    try:
        # Load from local parquet (located in repo root)
        if os.path.exists(DEFAULT_LOCAL_PARQUET):
            df = pd.read_parquet(DEFAULT_LOCAL_PARQUET)
            
            # Normalize columns
            df = df.rename(columns=CANON_COLS)
            
            # Ensure data types
            if "fecha" in df.columns:
                df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
            if "precio" in df.columns:
                df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
            if "año" in df.columns:
                df["año"] = pd.to_numeric(df["año"], errors="coerce")
            
            st.success(f"✅ Datos cargados: {len(df):,} registros")
            return df
        else:
            st.error(f"❌ Archivo no encontrado: {DEFAULT_LOCAL_PARQUET}")
            return None
    
    except Exception as e:
        st.error(f"❌ Error cargando datos: {str(e)}")
        return None


def ensure_required_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure required columns exist in dataframe.
    
    Args:
        df: Input dataframe
    
    Returns:
        Normalized dataframe with required columns
    """
    if df is None or df.empty:
        return df
    
    # Rename columns using canonicalization
    df = df.rename(columns=str.upper).rename(columns=CANON_COLS)
    
    # Check minimum required columns
    required = ["marca", "precio", "fecha"]
    missing = [col for col in required if col not in df.columns]
    
    if missing:
        st.warning(f"⚠️ Columnas faltantes: {missing}. Algunos análisis no funcionarán.")
    
    # Ensure proper data types
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    
    if "precio" in df.columns:
        df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
    
    if "año" in df.columns:
        df["año"] = pd.to_numeric(df["año"], errors="coerce")
    
    # Remove rows with missing critical values
    for col in required:
        if col in df.columns:
            df = df.dropna(subset=[col])
    
    return df


def apply_time_view(
    df: pd.DataFrame,
    start_date: object,
    end_date: object
) -> pd.DataFrame:
    """
    Filter dataframe by date range.
    
    Args:
        df: Input dataframe
        start_date: Start date (datetime or similar)
        end_date: End date (datetime or similar)
    
    Returns:
        Filtered dataframe
    """
    if df is None or df.empty or "fecha" not in df.columns:
        return df
    
    try:
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        return df[(df["fecha"] >= start) & (df["fecha"] <= end)].copy()
    
    except Exception as e:
        st.error(f"Error applying time filter: {str(e)}")
        return df


# =============================================================================
# DATA CLEANING
# =============================================================================

def etl_clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and validate data.
    
    Args:
        df: Raw dataframe
    
    Returns:
        Cleaned dataframe
    """
    if df is None or df.empty:
        return df
    
    df = df.copy()
    
    # Remove duplicates
    df = df.drop_duplicates()
    
    # Remove rows where precio is null or 0
    if "precio" in df.columns:
        df = df[df["precio"].notna() & (df["precio"] > 0)]
    
    # Remove rows where fecha is null
    if "fecha" in df.columns:
        df = df[df["fecha"].notna()]
    
    return df.reset_index(drop=True)

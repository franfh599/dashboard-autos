# -*- coding: utf-8 -*-
"""
Market Suite | Analytics Module

Provides business analytics and KPI calculations.
Previously in: app.py (monolithic)
"""

from __future__ import annotations
from typing import List, Optional, Tuple
import numpy as np
import pandas as pd
import streamlit as st


# ==============================================================================
# ANALYTICS FUNCTIONS
# ==============================================================================

@st.cache_data(show_spinner=False)
def agg_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate data by year-month to get monthly totals."""
    m = df.groupby(["AÑO", "MES_NUM"])["CANTIDAD"].sum().reset_index()
    m["Fecha"] = pd.to_datetime(
        m["AÑO"].astype(str) + "-" + m["MES_NUM"].astype(str) + "-01",
        errors="coerce"
    )
    return m.dropna(subset=["Fecha"])


@st.cache_data(show_spinner=False)
def top_share(df: pd.DataFrame, dim: str, top_n: int = 15) -> pd.DataFrame:
    """Get top N items by dimension with market share percentages."""
    t = df.groupby(dim)["CANTIDAD"].sum().sort_values(ascending=False).head(top_n).reset_index()
    denom = t["CANTIDAD"].sum()
    t["Share"] = (t["CANTIDAD"] / denom * 100) if denom else 0
    return t


def linear_regression_forecast(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """
    Simple linear regression for forecasting.
    Returns (slope, intercept) where y = slope*x + intercept
    
    Args:
        x: Independent variable (e.g., month numbers 1..12)
        y: Dependent variable (e.g., sales volumes)
    
    Returns:
        Tuple of (slope, intercept) for the fitted line
    """
    if len(x) < 2 or np.all(y == y[0]):
        return 0.0, float(y.mean()) if len(y) else 0.0
    
    m, b = np.polyfit(x, y, 1)
    return float(m), float(b)


def yoy_table(
    df_main: pd.DataFrame,
    df_view: pd.DataFrame,
    dim_col: str,
    sel_years: List[int]
) -> Optional[pd.DataFrame]:
    """
    Build Year-over-Year comparison table.
    Compares max selected year vs previous year (n-1).
    
    Args:
        df_main: Full dataset (for previous year lookup)
        df_view: Filtered dataset (current view)
        dim_col: Dimension column (MARCA, MODELO, COMBUSTIBLE, etc)
        sel_years: List of selected years
    
    Returns:
        DataFrame with YoY metrics or None if insufficient data
    """
    if len(sel_years) < 2:
        return None
    
    curr_y = int(max(sel_years))
    prev_y = int(curr_y - 1)
    
    df_curr = df_view[df_view["AÑO"] == curr_y]
    df_prev = df_main[df_main["AÑO"] == prev_y]
    
    if df_curr.empty and df_prev.empty:
        return None
    
    # Group current year
    grp_curr = df_curr.groupby(dim_col).agg(
        Vol_Actual=("CANTIDAD", "sum"),
        CIF_Actual=("VALOR US$ CIF", "sum"),
    ).reset_index()
    
    # Group previous year
    grp_prev = df_prev.groupby(dim_col).agg(
        Vol_Prev=("CANTIDAD", "sum"),
        CIF_Prev=("VALOR US$ CIF", "sum"),
    ).reset_index()
    
    # Calculate share percentages
    if grp_curr["Vol_Actual"].sum() > 0:
        grp_curr["Share_Actual"] = grp_curr["Vol_Actual"] / grp_curr["Vol_Actual"].sum() * 100
    else:
        grp_curr["Share_Actual"] = 0
    
    if grp_prev["Vol_Prev"].sum() > 0:
        grp_prev["Share_Prev"] = grp_prev["Vol_Prev"] / grp_prev["Vol_Prev"].sum() * 100
    else:
        grp_prev["Share_Prev"] = 0
    
    # Merge
    out = pd.merge(grp_curr, grp_prev, on=dim_col, how="outer").fillna(0)
    
    # Calculate deltas
    out["Δ Share (pp)"] = out["Share_Actual"] - out["Share_Prev"]
    out["Δ Inversión ($)"] = out["CIF_Actual"] - out["CIF_Prev"]
    out["Estado"] = np.where(out["Δ Share (pp)"] >= 0, "🟪 Ganó", "🔻 Perdió")
    
    return out

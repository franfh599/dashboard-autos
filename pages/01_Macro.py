"""Macro Analysis - Market Overview Page"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

#frm market_suite.state import init_session_state, clear_figure_registry
from market_suite.data import load_data_flow, apply_time_view, ensure_required_columns
from market_suite.analytics import agg_monthly, top_share, yoy_table, linear_regression_forecast
from market_suite.ui import sidebar_common, render_page_header, render_figure_with_registry, show_loading_spinner

# Configure page
st.set_page_config(
    page_title="Macro Analysis",
    page_icon="📊",
    layout="wide"
)

# Initialize session state
init_session_state()

# Clear previous figures from registry
clear_figure_registry()

# Render sidebar and get filters
sidebar_state = sidebar_common()

# Page header
render_page_header(
    title="Macro Analysis",
    description="Market-level analysis and comprehensive statistics",
    icon="📊"
)

with show_loading_spinner("Cargando datos de mercado..."):
    # Load data
    df_data = load_data_flow()
    
    if df_data is None or df_data.empty:
        st.error("❌ No data loaded. Check data connection.")
        st.stop()
    
    # Ensure required columns
    df_data = ensure_required_columns(df_data)
    
    # Apply time filter
    df_filtered = apply_time_view(
        df_data,
        sidebar_state["start_date"],
        sidebar_state["end_date"]
    )
    
    if df_filtered.empty:
        st.warning(f"⚠️ No data for selected date range: {sidebar_state['start_date']} to {sidebar_state['end_date']}")
        st.stop()

# Display KPI metrics
st.header("📈 Market Overview")
col1, col2, col3 = st.columns(3)

with col1:
    unique_markets = df_filtered["marca"].nunique() if "marca" in df_filtered.columns else 0
    st.metric(
        label="Total Markets",
        value=f"{unique_markets}",
        delta="Active brands in period"
    )

with col2:
    total_listings = len(df_filtered)
    st.metric(
        label="Total Listings",
        value=f"{total_listings:,}",
        delta="Records in period"
    )

with col3:
    avg_price = df_filtered["precio"].mean() if "precio" in df_filtered.columns else 0
    st.metric(
        label="Avg Price",
        value=f"${avg_price:,.0f}",
        delta="Mean listing price"
    )

# Monthly aggregation
st.header("📅 Monthly Trend")
try:
    df_monthly = agg_monthly(df_filtered, "precio")
    if df_monthly is not None and not df_monthly.empty:
        fig_monthly = df_monthly.plot()
        render_figure_with_registry(fig_monthly, "monthly_trend")
    else:
        st.info("No monthly data available for current date range.")
except Exception as e:
    st.error(f"Error creating monthly chart: {str(e)}")

# Top brands by share
st.header("🏆 Top Brands")
try:
    df_top_share = top_share(df_filtered, "marca", top_n=10)
    if df_top_share is not None and not df_top_share.empty:
        fig_top = df_top_share.plot(kind="barh")
        render_figure_with_registry(fig_top, "top_brands")
    else:
        st.info("No brand share data available.")
except Exception as e:
    st.error(f"Error creating brands chart: {str(e)}")

# Year-over-year comparison
st.header("📊 Year-over-Year")
try:
    if "fecha" in df_filtered.columns:
        # Create previous year data for comparison
        df_yoy = yoy_table(df_filtered, "fecha", "precio")
        if df_yoy is not None and not df_yoy.empty:
            st.dataframe(df_yoy, use_container_width=True)
        else:
            st.info("Insufficient data for YoY comparison.")
    else:
        st.warning("Date column required for YoY analysis.")
except Exception as e:
    st.error(f"Error creating YoY analysis: {str(e)}")

# Forecast
st.header("🔮 Price Forecast (Next 30 days)")
try:
    if "fecha" in df_filtered.columns and "precio" in df_filtered.columns:
        df_forecast = linear_regression_forecast(df_filtered, periods=30)
        if df_forecast is not None and not df_forecast.empty:
            fig_forecast = df_forecast.plot()
            render_figure_with_registry(fig_forecast, "price_forecast")
        else:
            st.info("Insufficient historical data for forecast.")
    else:
        st.warning("Date and price columns required for forecast.")
except Exception as e:
    st.error(f"Error creating forecast: {str(e)}")

# Export section
if sidebar_state["export_pdf"]:
    st.info("📥 PDF export triggered - figures registered for export")
    st.caption("Use the PDF button in sidebar to download all charts")

if sidebar_state["export_excel"]:
    try:
        buffer = df_filtered.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=buffer,
            file_name=f"macro_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
        st.success("✅ Excel export ready")
    except Exception as e:
        st.error(f"Error generating export: {str(e)}")

st.divider()
st.caption("Macro Analysis Dashboard v2.0 - Powered by market_suite")

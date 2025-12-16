"""Benchmark Analysis - Market Comparison Page"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

#frm market_suite.state import init_session_state, clear_figure_registry
from market_suite.data import load_data_flow, apply_time_view, ensure_required_columns
from market_suite.analytics import agg_monthly, top_share, yoy_table
from market_suite.ui import sidebar_common, render_page_header, render_figure_with_registry, show_loading_spinner

# Configure page
st.set_page_config(
    page_title="Benchmark Analysis",
    page_icon="🏆",
    layout="wide"
)

# Initialize session state
#init_session_state()

# Clear previous figures from registry
#clear_figure_registry()

# Render sidebar and get filters
#sidebar_state = sidebar_common()

# Page header
render_page_header(
    title="Benchmark Analysis",
    description="Compare market segments, competitors, and performance indicators",
    icon="🏆"
)

with show_loading_spinner("Cargando datos de benchmarking..."):
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

# Create tabs for different benchmark views
tab1, tab2, tab3, tab4 = st.tabs(["Price Benchmarking", "Market Share", "Performance", "Competitor Analysis"])

# Tab 1: Price Benchmarking
with tab1:
    st.header("💳 Price Analysis")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        min_price = df_filtered["precio"].min() if "precio" in df_filtered.columns else 0
        st.metric(label="Min Price", value=f"${min_price:,.0f}")
    
    with col2:
        max_price = df_filtered["precio"].max() if "precio" in df_filtered.columns else 0
        st.metric(label="Max Price", value=f"${max_price:,.0f}")
    
    with col3:
        median_price = df_filtered["precio"].median() if "precio" in df_filtered.columns else 0
        st.metric(label="Median Price", value=f"${median_price:,.0f}")
    
    # Price distribution by brand
    if "marca" in df_filtered.columns and "precio" in df_filtered.columns:
        try:
            df_price_by_brand = df_filtered.groupby("marca")["precio"].agg(["mean", "count"]).sort_values("mean", ascending=False).head(10)
            fig_price = df_price_by_brand["mean"].plot(kind="barh", title="Average Price by Brand")
            render_figure_with_registry(fig_price, "price_by_brand")
        except Exception as e:
            st.error(f"Error creating price chart: {str(e)}")

# Tab 2: Market Share
with tab2:
    st.header("📊 Market Share")
    
    try:
        df_share = top_share(df_filtered, "marca", top_n=15)
        if df_share is not None and not df_share.empty:
            fig_share = df_share.plot(kind="bar", title="Market Share by Brand")
            render_figure_with_registry(fig_share, "market_share")
            
            st.subheader("Share Data")
            st.dataframe(df_share, use_container_width=True)
        else:
            st.info("No market share data available.")
    except Exception as e:
        st.error(f"Error creating market share chart: {str(e)}")

# Tab 3: Performance Metrics
with tab3:
    st.header("📈 Performance Indicators")
    
    try:
        # Create performance summary
        if "marca" in df_filtered.columns:
            perf_summary = df_filtered.groupby("marca").agg({
                "precio": ["count", "mean", "std"]
            }).round(2)
            
            # Flatten column names
            perf_summary.columns = [f"{col[0]}_{col[1]}" for col in perf_summary.columns]
            perf_summary = perf_summary.sort_values("precio_count", ascending=False).head(15)
            
            st.dataframe(perf_summary, use_container_width=True)
            
            # Visualization
            fig_perf = perf_summary["precio_mean"].plot(kind="barh", title="Performance: Avg Price by Brand")
            render_figure_with_registry(fig_perf, "performance_metrics")
        else:
            st.warning("Brand column not found.")
    except Exception as e:
        st.error(f"Error creating performance analysis: {str(e)}")

# Tab 4: Competitor Analysis
with tab4:
    st.header("🤔 Competitor Insights")
    
    try:
        # Top brands analysis
        st.subheader("Top 5 Competitors")
        top_brands = df_filtered["marca"].value_counts().head(5)
        
        for idx, (brand, count) in enumerate(top_brands.items(), 1):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{idx}. {brand}**")
            with col2:
                st.metric("Listings", count)
            
            # Brand-specific metrics
            brand_data = df_filtered[df_filtered["marca"] == brand]
            if "precio" in brand_data.columns:
                avg_price = brand_data["precio"].mean()
                st.caption(f"Avg Price: ${avg_price:,.0f}")
            st.divider()
    except Exception as e:
        st.error(f"Error in competitor analysis: {str(e)}")

# Export section
if sidebar_state["export_pdf"]:
    st.info("📥 PDF export triggered - figures registered for export")
    st.caption("Use the PDF button in sidebar to download all benchmark charts")

if sidebar_state["export_excel"]:
    try:
        buffer = df_filtered.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=buffer,
            file_name=f"benchmark_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
        st.success("✅ Export ready")
    except Exception as e:
        st.error(f"Error generating export: {str(e)}")

st.divider()
st.caption("Benchmark Analysis Dashboard v2.0 - Powered by market_suite")

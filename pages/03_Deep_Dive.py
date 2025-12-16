"""Deep Dive Analysis - Detailed Market Segment Analysis Page"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

#from market_suite.state import init_session_state, clear_figure_registry
#from market_suite.data import load_data_flow, apply_time_view, ensure_required_columns
#from market_suite.analytics import agg_monthly, top_share
#from market_suite.ui import sidebar_common, render_page_header, render_figure_with_registry, show_loading_spinner

# Configure page
st.set_page_config(
    page_title="Deep Dive Analysis",
    page_icon="🔍",
    layout="wide"
)

# Initialize session state
#init_session_state()

# Clear previous figures from registry
#clear_figure_registry()

# Render sidebar and get filters
sidebar_state = sidebar_common()

# Page header
render_page_header(
    title="Deep Dive Analysis",
    description="Detailed analysis of specific market segments, products, and trends",
    icon="🔍"
)

with show_loading_spinner("Cargando datos detallados..."):
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

# Create expandable sections for detailed analysis
with st.expander("📊 Market Segment Analysis", expanded=True):
    st.header("Market Segments")
    
    if "marca" in df_filtered.columns:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Top Brands by Volume")
            brand_counts = df_filtered["marca"].value_counts().head(10)
            fig_volume = brand_counts.plot(kind="barh", title="Listings by Brand")
            render_figure_with_registry(fig_volume, "brand_volume")
        
        with col2:
            st.subheader("Market Concentration")
            top5_share = (brand_counts.head(5).sum() / len(df_filtered) * 100)
            st.metric(label="Top 5 Brands Share", value=f"{top5_share:.1f}%")
            st.metric(label="Total Brands", value=df_filtered["marca"].nunique())
            st.metric(label="Avg Listings/Brand", value=f"{len(df_filtered) / df_filtered['marca'].nunique():.0f}")
    else:
        st.warning("Brand column not found.")

# Price analysis by segment
with st.expander("💳 Price Segment Analysis", expanded=False):
    st.header("Price Distribution")
    
    if "precio" in df_filtered.columns:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Min Price", f"${df_filtered['precio'].min():,.0f}")
        with col2:
            st.metric("Median Price", f"${df_filtered['precio'].median():,.0f}")
        with col3:
            st.metric("Max Price", f"${df_filtered['precio'].max():,.0f}")
        
        # Price histogram
        st.subheader("Price Distribution")
        fig_price_dist = df_filtered["precio"].plot(kind="hist", bins=50, title="Price Distribution")
        render_figure_with_registry(fig_price_dist, "price_distribution")
        
        # Price by brand analysis
        st.subheader("Average Price by Brand")
        if "marca" in df_filtered.columns:
            price_by_brand = df_filtered.groupby("marca")["precio"].agg(["mean", "count"]).sort_values("mean", ascending=False).head(15)
            fig_price_brand = price_by_brand["mean"].plot(kind="barh", title="Avg Price by Brand (Top 15)")
            render_figure_with_registry(fig_price_brand, "price_by_brand_deepdive")
    else:
        st.warning("Price column not found.")

# Trend analysis
with st.expander("📅 Temporal Trends", expanded=False):
    st.header("Market Trends Over Time")
    
    if "fecha" in df_filtered.columns and "precio" in df_filtered.columns:
        try:
            # Monthly trend
            df_monthly = df_filtered.set_index("fecha").resample("M")["precio"].agg(["count", "mean", "std"])
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Monthly Listings")
                fig_monthly_count = df_monthly["count"].plot(title="Listings per Month")
                render_figure_with_registry(fig_monthly_count, "monthly_listings")
            
            with col2:
                st.subheader("Monthly Average Price")
                fig_monthly_price = df_monthly["mean"].plot(title="Avg Price per Month")
                render_figure_with_registry(fig_monthly_price, "monthly_avg_price")
            
            # Detailed trend table
            st.subheader("Monthly Statistics")
            st.dataframe(df_monthly.round(2), use_container_width=True)
        except Exception as e:
            st.error(f"Error creating temporal analysis: {str(e)}")
    else:
        st.warning("Date and/or price columns required for temporal analysis.")

# Correlation analysis
with st.expander("🔗 Correlation Analysis", expanded=False):
    st.header("Data Relationships")
    
    try:
        # Get numeric columns for correlation
        numeric_cols = df_filtered.select_dtypes(include=["number"]).columns.tolist()
        
        if len(numeric_cols) > 1:
            # Correlation matrix
            corr_matrix = df_filtered[numeric_cols].corr()
            
            st.subheader("Correlation Matrix")
            st.dataframe(corr_matrix.round(3), use_container_width=True)
            
            # Visualize correlation
            fig_corr = corr_matrix.abs().sum().sort_values(ascending=False).plot(kind="barh", title="Feature Correlation Strength")
            render_figure_with_registry(fig_corr, "correlation_analysis")
        else:
            st.info("Insufficient numeric columns for correlation analysis.")
    except Exception as e:
        st.error(f"Error in correlation analysis: {str(e)}")

# Data quality section
with st.expander("📄 Data Quality Report", expanded=False):
    st.header("Data Quality Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Records", f"{len(df_filtered):,}")
    with col2:
        st.metric("Missing Values %", f"{(df_filtered.isnull().sum().sum() / (len(df_filtered) * len(df_filtered.columns)) * 100):.1f}%")
    with col3:
        st.metric("Columns", len(df_filtered.columns))
    with col4:
        st.metric("Date Range", f"{(sidebar_state['end_date'] - sidebar_state['start_date']).days} days")
    
    # Missing data by column
    st.subheader("Missing Data by Column")
    missing_data = df_filtered.isnull().sum()
    if missing_data.sum() > 0:
        fig_missing = missing_data[missing_data > 0].plot(kind="barh", title="Missing Values by Column")
        render_figure_with_registry(fig_missing, "missing_data")
    else:
        st.success("✅ No missing data found!")

# Raw data inspector
with st.expander("📡 Raw Data Inspector", expanded=False):
    st.header("Data Preview & Download")
    
    # Display sample data
    st.subheader("Sample Data (First 100 Rows)")
    st.dataframe(df_filtered.head(100), use_container_width=True)
    
    # Download options
    st.subheader("Export Data")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        csv = df_filtered.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"deepdive_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with col2:
        try:
            excel = df_filtered.to_excel(index=False)
            st.download_button(
                label="📊 Download Excel",
                data=excel,
                file_name=f"deepdive_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.warning(f"Excel export not available: {str(e)}")
    
    with col3:
        json_data = df_filtered.to_json(orient="records", date_format="iso")
        st.download_button(
            label="📁 Download JSON",
            data=json_data,
            file_name=f"deepdive_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

# Export section
if sidebar_state["export_pdf"]:
    st.info("📥 PDF export triggered - all figures have been registered for export")
    st.caption("Use the PDF button in sidebar to download complete analysis")

if sidebar_state["export_excel"]:
    st.success("✅ Export functionality available in the 'Raw Data Inspector' section above")

st.divider()
st.caption("Deep Dive Analysis Dashboard v2.0 - Powered by market_suite")

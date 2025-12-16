"""Common UI components and helpers for Streamlit dashboard."""

import streamlit as st
from datetime import datetime, timedelta
import pandas as pd


def sidebar_common():
    """
    Renders common sidebar elements across all pages:
    - Date range selector
    - Export buttons (PDF, Excel)
    - Theme selector
    
    Returns:
        dict: Contains selected_start_date, selected_end_date, and other UI state
    """
    with st.sidebar:
        st.header("🔧 Filtros")
        
        # Date range selector
        col1, col2 = st.columns(2)
        with col1:
            selected_start_date = st.date_input(
                "Desde:",
                value=datetime.now() - timedelta(days=365),
                key="sidebar_start_date"
            )
        with col2:
            selected_end_date = st.date_input(
                "Hasta:",
                value=datetime.now(),
                key="sidebar_end_date"
            )
        
        st.divider()
        
        # Export section
        st.subheader("📥 Exportar")
        col1, col2 = st.columns(2)
        
        export_pdf = col1.button("📄 PDF", key="export_pdf_btn", use_container_width=True)
        export_excel = col2.button("📊 Excel", key="export_excel_btn", use_container_width=True)
        
        st.divider()
        
        # Theme selector
        st.subheader("🎨 Tema")
        theme = st.radio(
            "Selecciona tema:",
            options=["Automático", "Claro", "Oscuro"],
            key="theme_selector",
            index=0
        )
        
        st.divider()
        st.caption("Dashboard de Autos v2.0")
        
        return {
            "start_date": selected_start_date,
            "end_date": selected_end_date,
            "export_pdf": export_pdf,
            "export_excel": export_excel,
            "theme": theme
        }


def render_kpi_card(label: str, value: str, delta: str = None, color: str = "blue"):
    """
    Renders a KPI card with label, value, and optional delta.
    
    Args:
        label: KPI label
        value: KPI value (formatted string)
        delta: Optional delta/change indicator
        color: Card color theme
    """
    col = st.container(border=True)
    with col:
        st.metric(label=label, value=value, delta=delta)


def render_page_header(title: str, description: str = None, icon: str = "📊"):
    """
    Renders a standardized page header.
    
    Args:
        title: Page title
        description: Optional page description
        icon: Emoji or icon for title
    """
    st.title(f"{icon} {title}")
    if description:
        st.markdown(f"*{description}*")
    st.divider()


def show_loading_spinner(message: str = "Cargando datos..."):
    """
    Context manager for loading spinner.
    
    Usage:
        with show_loading_spinner():
            # Long-running operation
            pass
    """
    return st.spinner(message)


def render_figure_with_registry(fig, name: str, show_title: bool = True):
    """
    Renders a Plotly figure and registers it for PDF export.
    
    Args:
        fig: Plotly figure object
        name: Figure name for registry and PDF export
        show_title: Whether to show figure title
    """
    from market_suite.state import register_figure
    
    # Register figure for PDF export
    register_figure(fig, name)
    
    # Display figure
    st.plotly_chart(fig, use_container_width=True, key=f"fig_{name}")


def export_figures_to_pdf(filename: str = "dashboard_export.pdf"):
    """
    Exports all registered figures to PDF.
    Requires kaleido library: pip install kaleido
    
    Args:
        filename: Output PDF filename
    
    Returns:
        bytes: PDF file content or None if no figures registered
    """
    from market_suite.state import get_registered_figures
    import plotly.io as pio
    from io import BytesIO
    
    figures = get_registered_figures()
    if not figures:
        st.warning("No figures registered for export.")
        return None
    
    try:
        # Combine all figures into single PDF
        pdf_buffer = BytesIO()
        for idx, (name, fig) in enumerate(figures.items()):
            pdf_bytes = pio.to_image(fig, format="pdf", engine="kaleido")
            if idx == 0:
                pdf_buffer.write(pdf_bytes)
            else:
                # Append subsequent pages
                pdf_buffer.write(pdf_bytes)
        
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()
    
    except ImportError:
        st.error("Kaleido no instalado. Ejecuta: pip install kaleido")
        return None
    except Exception as e:
        st.error(f"Error al exportar PDF: {str(e)}")
        return None

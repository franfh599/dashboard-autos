# -*- coding: utf-8 -*-
"""
EV Market Intelligence Suite | Streamlit App
Home Page

Portada y guía rápida de navegación.
"""

import streamlit as st

# Configuración de la página
st.set_page_config(
    page_title="EV Market Intelligence Suite",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS personalizado para mejorar la estética
st.markdown(
    """
    <style>
    .main {
        padding: 2rem 1rem;
    }
    .stTitle {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .stSubheader {
        font-size: 1.5rem;
        color: #333;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Encabezado
st.title("🚗 EV Market Intelligence Suite")
st.markdown("---")

# Sección de bienvenida
with st.container():
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(
            """
            ## Bienvenido
            
            Esta es la suite de análisis completa para inteligencia de mercado de vehículos eléctricos.
            Accede a los diferentes módulos usando el menú lateral.
            """
        )
    
    with col2:
        st.info(
            "💡 **Tip:** Utiliza el menú lateral para navegar entre las diferentes secciones."
        )

st.markdown("---")

# Descripción de módulos disponibles
st.subheader("📈 Módulos Disponibles")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        ### 📈 Macro
        
        Análisis macroeconómico y tendencias del mercado de EV.
        - Evolución de ventas
        - Penetración de mercado
        - Pronósticos YoY
        """
    )

with col2:
    st.markdown(
        """
        ### 🎯 Benchmark
        
        Comparación entre marcas y modelos.
        - Posicionamiento competitivo
        - Análisis de cuota de mercado
        - Métricas de desempeño
        """
    )

with col3:
    st.markdown(
        """
        ### 🔍 Deep Dive
        
        Análisis profundo de segmentos específicos.
        - Análisis por modelo
        - Detalles de mercado
        - Reportes personalizados
        """
    )

st.markdown("---")

# Sección de características principales
st.subheader("✨ Características Principales")

feat_col1, feat_col2 = st.columns(2)

with feat_col1:
    st.success("✅ Datos actualizados regularmente")
    st.success("✅ Análisis en tiempo real")
    st.success("✅ Exportación a PDF")

with feat_col2:
    st.success("✅ Gráficos interactivos")
    st.success("✅ Comparativas YoY")
    st.success("✅ Múltiples vistas de datos")

st.markdown("---")

# Footer
st.markdown(
    """
    <div style='text-align: center; color: #666; margin-top: 3rem;'>
        <p>EV Market Intelligence Suite © 2024</p>
        <p style='font-size: 0.9rem;'>Datos basados en análisis de mercado actualizado</p>
    </div>
    """,
    unsafe_allow_html=True,
)

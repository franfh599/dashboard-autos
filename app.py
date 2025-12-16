# -*- coding: utf-8 -*-
"""
EV Market Intelligence Suite | Streamlit App
Monolithic Application Version

Portada y guía rápida de navegación.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

# --- CONFIGURATION DE LA PÁGINA ---
st.set_page_config(
    page_title="EV Market Intelligence",
    layout="wide",
    page_icon="🚗",
    initial_sidebar_state="expanded"
)

# --- ESTILOS VISUALES ---
st.markdown("""
<style>
    .main {
        background-color: #f8f9fa;
    }
    .stTitle {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: white;
        padding: 2rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- DATOS DE EJEMPLO ---
@st.cache_data
def load_sample_data():
    """Carga datos de ejemplo para las visualizaciones"""
    dates = pd.date_range(start='2023-01-01', end='2024-12-31', freq='D')
    data = {
        'date': dates,
        'ev_sales': np.random.randint(100, 500, len(dates)),
        'market_share': np.random.uniform(10, 50, len(dates)),
        'avg_price': np.random.uniform(30000, 80000, len(dates))
    }
    return pd.DataFrame(data)

# --- PAGINA PRINCIPAL ---
def page_home():
    st.title("🚗 EV Market Intelligence Suite")
    st.markdown("""---""")
    
    st.markdown("""
    ### Bienvenido al Dashboard de Inteligencia de Mercado de Vehículos Eléctricos
    
    Esta aplicación monolítica proporciona:
    - **Análisis Macro**: Tendencias del mercado global de VE
    - **Benchmark**: Comparación de competidores y modelos
    - **Análisis Profundo**: Deep Dive en segmentos específicos
    """)
    
    st.markdown("---")
    st.subheader("Datos de Ejemplo")
    
    df = load_sample_data()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="Total Ventas EV",
            value=f"{df['ev_sales'].sum():,}",
            delta="+12.5%"
        )
    with col2:
        st.metric(
            label="Promedio Market Share",
            value=f"{df['market_share'].mean():.1f}%",
            delta="+2.3%"
        )
    with col3:
        st.metric(
            label="Precio Promedio",
            value=f"${df['avg_price'].mean():,.0f}",
            delta="-3.2%"
        )
    with col4:
        st.metric(
            label="Actualización",
            value=datetime.now().strftime("%d/%m/%Y")
        )
    
    st.markdown("---")
    st.subheader("Gráficos de Tendencias")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfico de vendidas
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=df['date'],
            y=df['ev_sales'],
            mode='lines',
            name='Ventas EV',
            line=dict(color='#1f77b4')
        ))
        fig1.update_layout(
            title="Ventas de VE en el Tiempo",
            xaxis_title="Fecha",
            yaxis_title="Ventas (unidades)",
            template="plotly_white"
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        # Gráfico de market share
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=df['date'],
            y=df['market_share'],
            mode='lines',
            name='Market Share',
            line=dict(color='#ff7f0e')
        ))
        fig2.update_layout(
            title="Market Share de VE",
            xaxis_title="Fecha",
            yaxis_title="Market Share (%)",
            template="plotly_white"
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    st.markdown("---")
    st.subheader("Primeras 10 Filas de Datos")
    st.dataframe(df.head(10), use_container_width=True)
    
    st.markdown("---")
    st.info(
        "🛠️  **Nota**: Esta es una versión monolítica simplificada. "
        "Todos los datos mostrados son ejemplos para demostración."
    )

# --- PAGINA MACRO ---
def page_macro():
    st.title("🌐 Análisis Macro")
    st.markdown("Análisis de tendencias globales del mercado de VE")
    
    df = load_sample_data()
    monthly_sales = df.set_index('date').resample('M')['ev_sales'].sum()
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=monthly_sales.index,
        y=monthly_sales.values,
        name='Ventas Mensuales',
        marker=dict(color='#2ca02c')
    ))
    fig.update_layout(
        title="Ventas de VE por Mes",
        xaxis_title="Mes",
        yaxis_title="Ventas (unidades)",
        template="plotly_white"
    )
    st.plotly_chart(fig, use_container_width=True)
    
    st.success("✅ Módulo de Análisis Macro operacional")

# --- PAGINA BENCHMARK ---
def page_benchmark():
    st.title("🏆 Benchmark")
    st.markdown("Comparación de competidores y modelos")
    
    df = load_sample_data()
    
    benchmark_data = {
        'Competidor': ['Tesla', 'BYD', 'VW', 'Hyundai', 'GM'],
        'Market Share': [28, 32, 12, 8, 7],
        'Modelos': [5, 12, 8, 6, 4]
    }
    benchmark_df = pd.DataFrame(benchmark_data)
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.pie(
            benchmark_df,
            values='Market Share',
            names='Competidor',
            title="Market Share por Competidor"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = px.bar(
            benchmark_df,
            x='Competidor',
            y='Modelos',
            title="Número de Modelos por Competidor",
            color='Modelos'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.dataframe(benchmark_df, use_container_width=True)
    st.success("✅ Módulo de Benchmark operacional")

# --- PAGINA DEEP DIVE ---
def page_deep_dive():
    st.title("🔍 Deep Dive Analysis")
    st.markdown("Análisis profundo por segmento")
    
    df = load_sample_data()
    
    segment = st.selectbox(
        "Selecciona un segmento:",
        ["Sedanes", "SUVs", "Hatchbacks", "Camionetas"]
    )
    
    st.write(f"Analizando segmento: **{segment}**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.line(
            df,
            x='date',
            y='avg_price',
            title=f"Precio Promedio - {segment}"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = px.area(
            df,
            x='date',
            y='market_share',
            title=f"Market Share - {segment}"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.info(f"🛠️  Mostrando datos para {segment}")
    st.success("✅ Módulo Deep Dive operacional")

# --- NAVEGACION CON SIDEBAR ---
st.sidebar.title("🤬 Navegación")
page = st.sidebar.radio(
    "Selecciona una página:",
    ["Home", "Macro", "Benchmark", "Deep Dive"]
)

if page == "Home":
    page_home()
elif page == "Macro":
    page_macro()
elif page == "Benchmark":
    page_benchmark()
elif page == "Deep Dive":
    page_deep_dive()

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Información")
st.sidebar.info(
    "Esta es una aplicación monolítica que integra todos los módulos "
    "en un único archivo app.py"
)

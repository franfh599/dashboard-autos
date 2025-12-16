import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import calendar
import os
import numpy as np
import gc
from datetime import datetime
from fpdf import FPDF

# ==============================================================================
# 1. CONFIGURACIÓN ESTRATÉGICA DE LA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="EV Market Intelligence Suite", 
    layout="wide", 
    page_icon="🧠",
    initial_sidebar_state="expanded"
)

# Inicialización de variables de estado para persistencia
if 'theme_mode' not in st.session_state:
    st.session_state['theme_mode'] = 'System'
if 'time_view' not in st.session_state:
    st.session_state['time_view'] = 'Full Year' # Opciones: Full Year, YTD

# ==============================================================================
# 2. SISTEMA DE DISEÑO RESPONSIVO (CSS AVANZADO)
# ==============================================================================
def inject_custom_css():
    """
    Inyecta estilos CSS que reaccionan al modo del navegador y permiten
    forzar modos oscuros/claros mediante botones sin romper la UI.
    """
    base_css = """
    <style>
        /* Ajuste de márgenes para maximizar espacio */
        .block-container {
            padding-top: 1.5rem; 
            padding-bottom: 5rem;
        }
        
        /* Pestañas (Tabs) Estilizadas */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            border-radius: 5px 5px 0px 0px;
            padding: 10px 20px;
            font-weight: 600;
        }
        
        /* Tarjetas de Métricas (KPI Cards) Flotantes */
        div[data-testid="stMetric"] {
            background-color: rgba(255, 255, 255, 0.03); 
            border: 1px solid rgba(128, 128, 128, 0.2);
            padding: 15px;
            border-radius: 10px;
            border-left: 5px solid #1e3799; /* Azul Corporativo */
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            transition: transform 0.2s;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-2px);
        }
    </style>
    """
    st.markdown(base_css, unsafe_allow_html=True)

    # Lógica de Forzado de Tema (Hack CSS seguro)
    if st.session_state['theme_mode'] == 'Dark Force':
        st.markdown("""
        <style>
            .stApp {
                background-color: #0e1117;
                color: #fafafa;
            }
            /* Invertir tablas para que sean legibles en oscuro si el navegador es claro */
            .stDataFrame { filter: invert(0); } 
        </style>
        """, unsafe_allow_html=True)
    elif st.session_state['theme_mode'] == 'Light Force':
        st.markdown("""
        <style>
            .stApp {
                background-color: #ffffff;
                color: #0f0f0f;
            }
        </style>
        """, unsafe_allow_html=True)

inject_custom_css()

# ==============================================================================
# 3. MOTOR DE DATOS BLINDADO (ETL & FECHAS)
# ==============================================================================
@st.cache_data(show_spinner=False)
def cargar_datos_robusto():
    """
    Carga el parquet, normaliza nombres, corrige tipos de datos y fechas.
    Retorna el DataFrame limpio y la última fecha registrada.
    """
    archivo = "historial_lite.parquet"
    if not os.path.exists(archivo): return None, None
    
    try:
        df = pd.read_parquet(archivo)
        df.columns = df.columns.str.strip().str.upper()
        
        # 1. Normalización de Textos (Evitar duplicados por mayúsculas/espacios)
        cols_txt = ['MARCA', 'MODELO', 'EMPRESA', 'COMBUSTIBLE', 'CARROCERIA', 'MES']
        for c in cols_txt:
            if c in df.columns: 
                df[c] = df[c].astype(str).str.strip().str.upper()
        
        # Corrección de Nombres de Marcas Comunes
        if 'MARCA' in df.columns:
            df['MARCA'] = df['MARCA'].replace({
                'M.G.': 'MG', 'MORRIS GARAGES': 'MG', 'M. G.': 'MG',
                'BYD AUTO': 'BYD', 'TOYOTA MOTOR': 'TOYOTA'
            })
            
        # 2. Conversión Numérica Segura
        for c in ['CANTIDAD', 'VALOR US$ CIF', 'FLETE']:
            if c in df.columns: 
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
                
        # 3. Ingeniería de Fechas (CRÍTICO)
        if 'FECHA' in df.columns:
            df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
            df = df.dropna(subset=['FECHA'])
            df['AÑO'] = df['FECHA'].dt.year.astype(int)
            df['MES_NUM'] = df['FECHA'].dt.month.astype(int)
            
            # Detectar última fecha real
            ultima_fecha = df['FECHA'].max()
        else:
            ultima_fecha = None

        # 4. KPIs Unitarios (Evitando división por cero)
        if 'VALOR US$ CIF' in df.columns:
            df['CIF_UNITARIO'] = (df['VALOR US$ CIF'] / df['CANTIDAD']).replace([np.inf, -np.inf], 0).fillna(0)
        if 'FLETE' in df.columns:
            df['FLETE_UNITARIO'] = (df['FLETE'] / df['CANTIDAD']).replace([np.inf, -np.inf], 0).fillna(0)
            
        return df, ultima_fecha
        
    except Exception as e:
        st.error(f"Error crítico cargando la base de datos: {e}")
        return None, None

def aplicar_logica_temporal(df, ultima_fecha):
    """
    Filtra el DataFrame según la selección YTD o Full Year.
    Si es YTD, recorta todos los años históricos al mes de la última fecha.
    """
    if st.session_state['time_view'] == 'YTD (Year to Date)' and ultima_fecha:
        mes_corte = ultima_fecha.month
        # Filtramos para que todos los años terminen en el mes de corte actual
        df_filtrado = df[df['MES_NUM'] <= mes_corte].copy()
        return df_filtrado
    
    return df

# ==============================================================================
# 4. MOTOR DE REPORTE PDF EJECUTIVO (LIGERO & RÁPIDO)
# ==============================================================================
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Reporte de Inteligencia de Mercado - Automotriz', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pag {self.page_no()} - Generado el {datetime.now().strftime("%Y-%m-%d")}', 0, 0, 'C')

def clean_text(text):
    """Limpia caracteres especiales para compatibilidad PDF"""
    try: return str(text).encode('latin-1', 'replace').decode('latin-1')
    except: return str(text)

@st.cache_data(show_spinner=False)
def generar_pdf_master(df_dict, titulo, subtitulo, view_mode):
    # Convertir dict a DataFrame (ligero)
    df = pd.DataFrame(df_dict)
    
    pdf = PDF()
    pdf.add_page()
    
    # 1. TÍTULO Y CONTEXTO
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, clean_text(titulo), 0, 1, 'L')
    pdf.set_font("Arial", 'I', 11)
    pdf.cell(0, 10, f"Vista: {clean_text(view_mode)} | {clean_text(subtitulo)}", 0, 1, 'L')
    pdf.ln(5)
    
    # 2. RESUMEN EJECUTIVO (Caja Gris)
    total_vol = df['CANTIDAD'].sum()
    total_val = df['VALOR US$ CIF'].sum()
    promedio = total_val / total_vol if total_vol else 0
    
    pdf.set_fill_color(240, 240, 240)
    pdf.rect(10, 45, 190, 20, 'F')
    pdf.set_y(50)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(63, 10, f"Volumen: {total_vol:,.0f} autos", 0, 0, 'C')
    pdf.cell(63, 10, f"Inversion: ${total_val/1e6:,.1f} M", 0, 0, 'C')
    pdf.cell(63, 10, f"Ticket Prom: ${promedio:,.0f}", 0, 1, 'C')
    pdf.ln(15)

    # 3. TABLA DINÁMICA (TOP 15)
    pdf.set_font("Arial", 'B', 12)
    # Detectamos la columna de agrupación principal
    if 'MODELO' in df.columns and len(df['MODELO'].unique()) > 1:
        agrupador = 'MODELO'
    elif 'MARCA' in df.columns:
        agrupador = 'MARCA'
    else:
        agrupador = 'AÑO'

    pdf.cell(0, 10, f"Top 15 {clean_text(agrupador)} por Volumen", 0, 1)
    
    # Encabezados Tabla
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(200, 200, 200)
    pdf.cell(140, 8, clean_text(agrupador), 1, 0, 'L', 1)
    pdf.cell(50, 8, "Volumen", 1, 1, 'R', 1)
    
    pdf.set_font("Arial", '', 10)
    top_data = df.groupby(agrupador)['CANTIDAD'].sum().sort_values(ascending=False).head(15)
    
    for nombre, val in top_data.items():
        pdf.cell(140, 8, clean_text(str(nombre))[:60], 1)
        pdf.cell(50, 8, f"{val:,.0f}", 1, 1, 'R')
    pdf.ln(5)
    
    # 4. IMPORTADORES (Si están disponibles)
    if 'EMPRESA' in df.columns:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Top 5 Importadores Clave", 0, 1)
        pdf.set_font("Arial", '', 10)
        top_imp = df.groupby('EMPRESA')['CANTIDAD'].sum().sort_values(ascending=False).head(5)
        for nombre, val in top_imp.items():
            pdf.cell(140, 8, clean_text(str(nombre))[:60], 1)
            pdf.cell(50, 8, f"{val:,.0f}", 1, 1, 'R')

    return pdf.output(dest='S').encode('latin-1')

# ==============================================================================
# 5. CARGA INICIAL Y BARRA LATERAL (CONTROL CENTER)
# ==============================================================================
df_raw, ultima_fecha_raw = cargar_datos_robusto()

with st.sidebar:
    st.title("🧠 Market Suite")
    
    if df_raw is not None:
        # Status del Sistema
        st.success("✅ Sistema Online")
        
        # VISUALIZACIÓN DE LA ÚLTIMA FECHA (Requisito)
        if ultima_fecha_raw:
            str_fecha = ultima_fecha_raw.strftime("%d-%b-%Y")
            st.info(f"📅 **Data actualizada al:**\n\n{str_fecha}")
        
        st.divider()

        # CONTROLES GLOBALES
        st.subheader("⚙️ Configuración")
        
        # Botones de Tema
        c_theme1, c_theme2 = st.columns(2)
        with c_theme1:
            if st.button("🌙 Dark"): st.session_state['theme_mode'] = 'Dark Force'
        with c_theme2:
            if st.button("☀️ Light"): st.session_state['theme_mode'] = 'Light Force'
            
        # Control de Tiempo (YOY / YTD)
        st.markdown("**Visión Temporal:**")
        time_mode = st.radio("Selecciona:", ["Full Year (Completo)", "YTD (Year to Date)"], label_visibility="collapsed")
        st.session_state['time_view'] = time_mode
        
        st.divider()
        
        # MENÚ DE NAVEGACIÓN
        st.subheader("📍 Módulos Estratégicos")
        menu = st.radio("Ir a:", 
                        ["🌍 1. Visión País (Macro)", 
                         "⚔️ 2. Guerra de Marcas (Benchmark)", 
                         "🔍 3. Auditoría de Marca (Deep Dive)"], label_visibility="collapsed")
        st.divider()
        
    else:
        st.error("⚠️ Error Crítico: No se encuentran los datos (historial_lite.parquet).")
        st.stop()

# ==============================================================================
# 6. MOTOR LÓGICO Y VISUALIZACIÓN
# ==============================================================================

# Aplicar filtro temporal global (YTD o Full)
df_main = aplicar_logica_temporal(df_raw, ultima_fecha_raw)

# Variables para exportación PDF (Se llenan según el módulo activo)
pdf_dataset = pd.DataFrame()
pdf_title = ""

# ------------------------------------------------------------------------------
# MÓDULO 1: VISIÓN PAÍS (MACRO)
# ------------------------------------------------------------------------------
if menu == "🌍 1. Visión País (Macro)":
    st.title(f"🌍 Visión País: {st.session_state['time_view']}")
    
    # Filtros de Contexto
    years_avail = sorted(df_main['AÑO'].unique(), reverse=True)
    sel_years = st.multiselect("Periodo de Análisis", years_avail, default=years_avail[:2])
    df_view = df_main[df_main['AÑO'].isin(sel_years)].copy()
    
    # --- HERRAMIENTAS 1-5 ---
    
    # 1. TERMÓMETRO DE MERCADO (KPIs)
    vol_actual = df_view['CANTIDAD'].sum()
    val_actual = df_view['VALOR US$ CIF'].sum()
    
    with st.container():
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Volumen Total", f"{vol_actual:,.0f}")
        k2.metric("Inversión CIF", f"${val_actual/1e6:,.1f} M")
        k3.metric("Ticket Promedio", f"${(val_actual/vol_actual if vol_actual else 0):,.0f}")
        k4.metric("Marcas Activas", f"{df_view['MARCA'].nunique()}")

    col_a, col_b = st.columns([2, 1])
    
    with col_a:
        # 2. TENDENCIA TEMPORAL (Time-Series)
        st.subheader("📈 Ritmo de Importación")
        mensual = df_view.groupby(['AÑO', 'MES_NUM'])['CANTIDAD'].sum().reset_index()
        # Creamos fecha artificial para ordenar el gráfico correctamente
        mensual['Fecha'] = pd.to_datetime(mensual['AÑO'].astype(str) + '-' + mensual['MES_NUM'].astype(str) + '-01')
        st.plotly_chart(px.line(mensual, x='Fecha', y='CANTIDAD', markers=True, color='AÑO'), use_container_width=True)
        
    with col_b:
        # 3. RADAR DE ELECTRIFICACIÓN (Energy Mix)
        st.subheader("⚡ Mix Energético")
        st.plotly_chart(px.pie(df_view, values='CANTIDAD', names='COMBUSTIBLE', hole=0.4), use_container_width=True)

    col_c, col_d = st.columns(2)
    with col_c:
        # 4. PIRÁMIDE DE PRECIOS (Segmentation)
        st.subheader("💰 Segmentación de Precios")
        bins = [0, 15000, 25000, 40000, 70000, 1000000]
        labels = ['Económico (<15k)', 'Masivo (15-25k)', 'Medio (25-40k)', 'Premium (40-70k)', 'Lujo (>70k)']
        df_view['SEGMENTO'] = pd.cut(df_view['CIF_UNITARIO'], bins=bins, labels=labels)
        seg = df_view.groupby('SEGMENTO', observed=True)['CANTIDAD'].sum().reset_index()
        st.plotly_chart(px.bar(seg, x='CANTIDAD', y='SEGMENTO', orientation='h', color='SEGMENTO'), use_container_width=True)

    # 5. MARKET SHARE DINÁMICO (Nueva Funcionalidad Requerida)
    st.markdown("---")
    st.subheader("🏆 Market Share & Crecimiento Anual (YoY)")
    
    # Botones de Agrupación
    dim_col = st.radio("Agrupar Top por:", ["MARCA", "MODELO", "COMBUSTIBLE", "CARROCERIA"], horizontal=True)
    
    # Lógica de Cálculo YoY (Year over Year)
    if len(sel_years) >= 2:
        curr_y = max(sel_years)
        prev_y = curr_y - 1 # Año inmediatamente anterior
        
        # Data Actual vs Data Anterior (respetando filtros YTD si están activos)
        df_curr = df_view[df_view['AÑO'] == curr_y]
        # Para el año anterior, usamos el dataframe principal filtrado por el año previo
        df_prev = df_main[df_main['AÑO'] == prev_y]
        
        # Agrupación
        grp_curr = df_curr.groupby(dim_col).agg(Vol_Actual=('CANTIDAD','sum'), CIF_Actual=('VALOR US$ CIF','sum')).reset_index()
        grp_prev = df_prev.groupby(dim_col).agg(Vol_Prev=('CANTIDAD','sum'), CIF_Prev=('VALOR US$ CIF','sum')).reset_index()
        
        # Cálculo de Share
        grp_curr['Share_Actual'] = (grp_curr['Vol_Actual'] / grp_curr['Vol_Actual'].sum()) * 100
        grp_prev['Share_Prev'] = (grp_prev['Vol_Prev'] / grp_prev['Vol_Prev'].sum()) * 100
        
        # Fusión (Merge)
        df_yoy = pd.merge(grp_curr, grp_prev, on=dim_col, how='outer').fillna(0)
        
        # Métricas de Variación (Requerimiento)
        df_yoy['Δ Share (pp)'] = df_yoy['Share_Actual'] - df_yoy['Share_Prev']
        df_yoy['Δ Inv ($)'] = df_yoy['CIF_Actual'] - df_yoy['CIF_Prev']
        
        # Visualización de Tabla
        st.dataframe(
            df_yoy.sort_values('Vol_Actual', ascending=False).head(50).style
            .format({
                'Vol_Actual': '{:,.0f}', 'Vol_Prev': '{:,.0f}', 
                'Share_Actual': '{:.1f}%', 'Share_Prev': '{:.1f}%', 
                'Δ Share (pp)': '{:+.1f}', 'CIF_Actual': '${:,.0f}', 'Δ Inv ($)': '${:+,.0f}'
            })
            .background_gradient(subset=['Vol_Actual'], cmap="Blues")
            .map(lambda v: 'color: green; font-weight: bold' if v > 0 else 'color: red; font-weight: bold', subset=['Δ Share (pp)', 'Δ Inv ($)']),
            use_container_width=True
        )
    else:
        st.info("Selecciona al menos 2 años para ver el análisis de crecimiento (YoY).")

    pdf_dataset = df_view
    pdf_title = "Reporte Macro Pais"


# ------------------------------------------------------------------------------
# MÓDULO 2: BENCHMARK (GUERRA DE MARCAS)
# ------------------------------------------------------------------------------
elif menu == "⚔️ 2. Guerra de Marcas (Benchmark)":
    st.title(f"⚔️ Benchmarking Competitivo: {st.session_state['time_view']}")
    
    with st.sidebar:
        st.markdown("### 🎯 Competidores")
        years_avail = sorted(df_main['AÑO'].unique(), reverse=True)
        sel_years = st.multiselect("Años a Comparar", years_avail, default=years_avail[:1])
        df_curr = df_main[df_main['AÑO'].isin(sel_years)]
        
        all_brands = sorted(df_curr['MARCA'].unique())
        if st.checkbox("Seleccionar Todas", value=False):
            sel_brands = all_brands
        else:
            default_top = df_curr['MARCA'].value_counts().head(3).index.tolist()
            sel_brands = st.multiselect("Marcas", all_brands, default=default_top)

    df_view = df_curr[df_curr['MARCA'].isin(sel_brands)].copy()
    
    if not df_view.empty:
        t1, t2, t3 = st.tabs(["Volumen & Mix", "Precios", "Auditoría Gris"])
        
        with t1:
            c1, c2 = st.columns(2)
            with c1:
                # 6. BATALLA DE VOLUMEN
                st.subheader("📊 Comparativo Volumen")
                st.plotly_chart(px.bar(df_view, x='MARCA', y='CANTIDAD', color='AÑO', barmode='group'), use_container_width=True)
            with c2:
                # 9. MIX DE COMBUSTIBLE POR MARCA (Nuevo Requerimiento)
                st.subheader("⚡ Mix de Combustible por Marca")
                # Gráfico apilado al 100% para ver estrategia
                st.plotly_chart(px.bar(df_view, x='MARCA', y='CANTIDAD', color='COMBUSTIBLE', title="Estrategia de Motorización", barmode='relative'), use_container_width=True)

        with t2:
            # 7. MATRIZ DE ESTRATEGIA DE PRECIOS
            st.subheader("💸 Estrategia de Precios")
            # Filtro visual de outliers extremos
            df_p = df_view[(df_view['CIF_UNITARIO'] > 1000) & (df_view['CIF_UNITARIO'] < 200000)]
            st.plotly_chart(px.box(df_p, x='MARCA', y='CIF_UNITARIO', color='MARCA', points="outliers"), use_container_width=True)

        with t3:
            st.subheader("🕵️ Detección de Fuga (Oficial vs Paralelo)")
            
            # Algoritmo Vectorizado de Detección
            gb = df_view.groupby(['MARCA', 'EMPRESA'])['CANTIDAD'].sum().reset_index()
            # Asumimos que el mayor importador es el Oficial
            lideres = gb.sort_values(['MARCA', 'CANTIDAD'], ascending=[True, False]).drop_duplicates('MARCA')
            lideres = lideres.rename(columns={'EMPRESA': 'LIDER_OFICIAL'})[['MARCA', 'LIDER_OFICIAL']]
            
            df_view = df_view.merge(lideres, on='MARCA', how='left')
            df_view['CANAL'] = np.where(df_view['EMPRESA'] == df_view['LIDER_OFICIAL'], 'OFICIAL', 'GRIS')
            
            c_g1, c_g2 = st.columns(2)
            with c_g1:
                # Gráfico Barras Apiladas
                resumen = df_view.groupby(['MARCA', 'CANAL'])['CANTIDAD'].sum().unstack().fillna(0).reset_index()
                st.plotly_chart(px.bar(resumen, x='MARCA', y=[c for c in ['OFICIAL', 'GRIS'] if c in resumen.columns], 
                                       title="Volumen Absoluto: Oficial vs Gris", 
                                       color_discrete_map={'OFICIAL':'#27ae60', 'GRIS':'#95a5a6'}), use_container_width=True)
            with c_g2:
                # NUEVO GRÁFICO DE % DE FUGA (Requerimiento)
                if 'GRIS' in resumen.columns:
                    resumen['Total'] = resumen['OFICIAL'] + resumen['GRIS']
                    resumen['% Fuga'] = (resumen['GRIS'] / resumen['Total']) * 100
                    
                    fig_pct = px.bar(resumen, x='MARCA', y='% Fuga', title="Ranking de Fuga (% Mercado Gris)", text_auto='.1f',
                                     color='% Fuga', color_continuous_scale='Reds')
                    st.plotly_chart(fig_pct, use_container_width=True)
                else:
                    st.info("No se detectó fuga relevante en las marcas seleccionadas.")
            
            # Tabla de detalle
            st.write("**Identidad del Distribuidor Oficial Detectado:**")
            st.dataframe(lideres.set_index('MARCA'), use_container_width=True)

    pdf_dataset = df_view
    pdf_title = "Reporte Competitivo"


# ------------------------------------------------------------------------------
# MÓDULO 3: DEEP DIVE (AUDITORÍA DE MARCA)
# ------------------------------------------------------------------------------
elif menu == "🔍 3. Auditoría de Marca (Deep Dive)":
    st.title(f"🔍 Auditoría Profunda: {st.session_state['time_view']}")
    
    with st.sidebar:
        st.markdown("### 🎯 Objetivo")
        y_dd = st.selectbox("Año Fiscal", sorted(df_main['AÑO'].unique(), reverse=True))
        df_y = df_main[df_main['AÑO'] == y_dd]
        
        brand_dd = st.selectbox("Marca a Auditar", sorted(df_y['MARCA'].unique()))
        df_view = df_y[df_y['MARCA'] == brand_dd].copy()

    if not df_view.empty:
        with st.container(border=True):
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Volumen", f"{df_view['CANTIDAD'].sum():,.0f}")
            k2.metric("CIF Promedio", f"${df_view['CIF_UNITARIO'].mean():,.0f}")
            k3.metric("Flete Promedio", f"${df_view['FLETE_UNITARIO'].mean():,.0f}")
            k4.metric("Modelos Activos", f"{df_view['MODELO'].nunique()}")
        
        tab_a, tab_b, tab_c = st.tabs(["Eficiencia (Pareto)", "Proyección", "Logística"])
        
        with tab_a:
            # 11. ANÁLISIS DE PARETO (80/20)
            st.subheader("11. Eficiencia de Portafolio (Pareto)")
            pareto = df_view.groupby('MODELO')['CANTIDAD'].sum().sort_values(ascending=False).reset_index()
            pareto['% Acum'] = (pareto['CANTIDAD'].cumsum() / pareto['CANTIDAD'].sum()) * 100
            pareto['Clasificación'] = np.where(pareto['% Acum'] <= 80, 'A (Vital)', 'B (Cola)')
            
            fig_p = px.bar(pareto, x='MODELO', y='CANTIDAD', color='Clasificación', 
                           color_discrete_map={'A (Vital)': '#27ae60', 'B (Cola)': '#95a5a6'})
            st.plotly_chart(fig_p, use_container_width=True)
            
        with tab_b:
            c_f1, c_f2 = st.columns(2)
            with c_f1:
                # 12. FORECAST MATEMÁTICO
                st.subheader("12. Proyección de Tendencia")
                mensual = df_view.groupby('MES_NUM')['CANTIDAD'].sum().reset_index()
                mensual['Fecha'] = pd.to_datetime(str(y_dd) + '-' + mensual['MES_NUM'].astype(str) + '-01')
                
                try:
                    fig_tr = px.scatter(mensual, x='Fecha', y='CANTIDAD', trendline="ols", trendline_color_override="red")
                    fig_tr.update_traces(mode='lines+markers')
                    st.plotly_chart(fig_tr, use_container_width=True)
                except:
                    st.line_chart(mensual.set_index('Fecha')['CANTIDAD'])

            with c_f2:
                # 14. EVOLUCIÓN TICKET
                st.subheader("14. Evolución de Precio (Ticket)")
                evol_precio = df_view.groupby('MES_NUM')['CIF_UNITARIO'].mean().reset_index()
                evol_precio['Fecha'] = pd.to_datetime(str(y_dd) + '-' + evol_precio['MES_NUM'].astype(str) + '-01')
                st.plotly_chart(px.line(evol_precio, x='Fecha', y='CIF_UNITARIO', markers=True), use_container_width=True)

        with tab_c:
            c_l1, c_l2 = st.columns(2)
            with c_l1:
                # 13. SEMÁFORO LOGÍSTICO
                st.subheader("13. Variabilidad Logística (Fletes)")
                fletes = df_view[(df_view['FLETE_UNITARIO'] > 50) & (df_view['FLETE_UNITARIO'] < 8000)]
                if not fletes.empty:
                    st.plotly_chart(px.box(fletes, y='FLETE_UNITARIO', title="Rango de Costo Flete"), use_container_width=True)
                else:
                    st.info("Sin datos de fletes válidos.")
            
            with c_l2:
                # 15. MAPA DE CALOR ESTACIONAL (SOLUCIÓN ERROR)
                # Reemplazamos la tabla con estilo pandas (que requiere matplotlib)
                # por un Heatmap interactivo de Plotly. ¡Mucho más robusto!
                st.subheader("15. Estacionalidad (Heatmap)")
                
                heatmap_data = df_view.groupby('MES_NUM')['CANTIDAD'].sum().reset_index()
                heatmap_data['Nombre_Mes'] = heatmap_data['MES_NUM'].apply(lambda x: calendar.month_abbr[x])
                
                # Gráfico de Calor Plotly (No falla)
                fig_heat = px.density_heatmap(heatmap_data, x="Nombre_Mes", y="CANTIDAD", nbinsx=12, nbinsy=1, 
                                              title="Intensidad de Importación por Mes", color_continuous_scale="Blues")
                # Ajuste visual para que parezca una barra de intensidad
                fig_heat.update_traces(hovertemplate='Mes: %{x}<br>Volumen: %{y}')
                st.plotly_chart(fig_heat, use_container_width=True)

    pdf_dataset = df_view
    pdf_title = f"Auditoria {brand_dd} ({y_dd})"


# ==============================================================================
# 7. EXPORTACIÓN PDF (BOTÓN SIEMPRE VISIBLE Y SEGURO)
# ==============================================================================
if 'pdf_dataset' in locals() and not pdf_dataset.empty:
    st.sidebar.divider()
    st.sidebar.markdown("### 📥 Exportar Reporte")
    
    try:
        # Optimización: Convertir DataFrame a Diccionario para caché rápido
        data_dict = pdf_dataset.to_dict(orient='list')
        
        # Generar PDF en segundo plano
        pdf_bytes = generar_pdf_master(
            data_dict, 
            pdf_title, 
            f"Modo: {st.session_state['time_view']}", 
            st.session_state['time_view']
        )
        
        # Botón de Descarga Directa
        st.sidebar.download_button(
            label="💾 Descargar PDF Ejecutivo",
            data=pdf_bytes,
            file_name=f"Reporte_{pdf_title.replace(' ','_')}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.sidebar.warning(f"No se pudo generar el PDF con los filtros actuales. Intenta reducir la selección.")

# Limpieza final de memoria RAM
gc.collect()

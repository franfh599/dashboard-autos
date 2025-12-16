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
# ==============================================================================
# 1. ARQUITECTURA Y CONFIGURACIÓN DEL SISTEMA
# ==============================================================================
# ==============================================================================

# Configuración inicial de la página con metadatos extendidos
st.set_page_config(
    page_title="EV Market Intelligence Suite | Enterprise", 
    layout="wide", 
    page_icon="🧠",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://www.streamlit.io',
        'Report a bug': "mailto:soporte@tuempresa.com",
        'About': "# Market Intelligence Suite v27.0\nHerramienta de análisis estratégico."
    }
)

# Inicialización segura de variables de estado (Session State)
# Esto garantiza que la configuración del usuario no se pierda al recargar gráficos.
if 'theme_mode' not in st.session_state:
    st.session_state['theme_mode'] = 'System'

if 'time_view' not in st.session_state:
    st.session_state['time_view'] = 'Full Year' # Opciones: Full Year, YTD

# ==============================================================================
# 2. SISTEMA DE DISEÑO AVANZADO (CSS INJECTION)
# ==============================================================================

def inject_custom_css():
    """
    Inyecta estilos CSS avanzados para controlar la apariencia de la interfaz.
    Maneja la lógica de modo Oscuro/Claro forzado y mejora la legibilidad
    de las tarjetas de métricas (KPIs).
    """
    
    # CSS Base: Define espaciados, bordes de pestañas y sombras.
    base_css = """
    <style>
        /* Ajuste del contenedor principal para maximizar el espacio útil */
        .block-container {
            padding-top: 1.5rem; 
            padding-bottom: 6rem;
        }
        
        /* Estilización de Pestañas (Tabs) */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            border-bottom: 1px solid rgba(128, 128, 128, 0.2);
            padding-bottom: 5px;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 45px;
            white-space: pre-wrap;
            border-radius: 6px 6px 0px 0px;
            padding: 8px 16px;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.2s ease-in-out;
        }
        
        /* Efecto Hover en Tabs */
        .stTabs [data-baseweb="tab"]:hover {
            background-color: rgba(128, 128, 128, 0.1);
        }
        
        /* Tarjetas de Métricas (KPI Cards) con efecto de cristal */
        div[data-testid="stMetric"] {
            background-color: rgba(255, 255, 255, 0.03); 
            border: 1px solid rgba(128, 128, 128, 0.15);
            padding: 20px;
            border-radius: 12px;
            border-left: 5px solid #1e3799; /* Azul Corporativo */
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        div[data-testid="stMetric"]:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 15px rgba(0, 0, 0, 0.1);
        }

        /* Ajuste de Dataframes para ocupar ancho completo */
        div[data-testid="stDataFrame"] {
            width: 100%;
        }
    </style>
    """
    st.markdown(base_css, unsafe_allow_html=True)

    # Lógica de Forzado de Tema (Hack CSS seguro para inversión de colores)
    if st.session_state['theme_mode'] == 'Dark Force':
        st.markdown("""
        <style>
            .stApp {
                background-color: #0e1117;
                color: #e0e0e0;
            }
            /* Invertir tablas nativas si es necesario para contraste */
            .stDataFrame { filter: invert(0); } 
            
            /* Ajuste de sidebar en modo oscuro */
            section[data-testid="stSidebar"] {
                background-color: #161b22;
                border-right: 1px solid #30363d;
            }
        </style>
        """, unsafe_allow_html=True)
        
    elif st.session_state['theme_mode'] == 'Light Force':
        st.markdown("""
        <style>
            .stApp {
                background-color: #ffffff;
                color: #1a1a1a;
            }
            section[data-testid="stSidebar"] {
                background-color: #f8f9fa;
                border-right: 1px solid #dee2e6;
            }
        </style>
        """, unsafe_allow_html=True)

# Ejecutar inyección de estilos al inicio
inject_custom_css()

# ==============================================================================
# ==============================================================================
# 3. CAPA DE DATOS (ETL & INGENIERÍA DE CARACTERÍSTICAS)
# ==============================================================================
# ==============================================================================

@st.cache_data(show_spinner=False)
def cargar_datos_robusto():
    """
    EXTRACT, TRANSFORM, LOAD (ETL):
    1. Carga el archivo Parquet de alto rendimiento.
    2. Normaliza nombres de columnas y datos string.
    3. Corrige tipos de datos numéricos.
    4. Genera columnas derivadas (Unitarios, Fechas).
    5. Maneja errores de archivo no encontrado.
    
    Returns:
        DataFrame: Datos limpios.
        Timestamp: La fecha más reciente encontrada en la base.
    """
    archivo_fuente = "historial_lite.parquet"
    
    # Validación de existencia del archivo
    if not os.path.exists(archivo_fuente):
        return None, None
    
    try:
        # Carga optimizada
        df = pd.read_parquet(archivo_fuente)
        
        # --- FASE 1: NORMALIZACIÓN DE TEXTO ---
        df.columns = df.columns.str.strip().str.upper()
        
        columnas_texto = ['MARCA', 'MODELO', 'EMPRESA', 'COMBUSTIBLE', 'CARROCERIA', 'MES']
        for col in columnas_texto:
            if col in df.columns: 
                df[col] = df[col].astype(str).str.strip().str.upper()
        
        # Diccionario de corrección de marcas (Data Cleaning)
        correcciones_marcas = {
            'M.G.': 'MG', 
            'MORRIS GARAGES': 'MG', 
            'M. G.': 'MG',
            'BYD AUTO': 'BYD', 
            'TOYOTA MOTOR': 'TOYOTA',
            'MB': 'MERCEDES-BENZ'
        }
        if 'MARCA' in df.columns:
            df['MARCA'] = df['MARCA'].replace(correcciones_marcas)
            
        # --- FASE 2: CONVERSIÓN NUMÉRICA ---
        columnas_numericas = ['CANTIDAD', 'VALOR US$ CIF', 'FLETE']
        for col in columnas_numericas:
            if col in df.columns: 
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
        # --- FASE 3: INGENIERÍA DE FECHAS ---
        if 'FECHA' in df.columns:
            df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
            # Eliminar filas huerfanas sin fecha
            df = df.dropna(subset=['FECHA'])
            
            # Crear dimensiones temporales
            df['AÑO'] = df['FECHA'].dt.year.astype(int)
            df['MES_NUM'] = df['FECHA'].dt.month.astype(int)
            
            # Detectar última fecha real para reportes de status
            ultima_fecha = df['FECHA'].max()
        else:
            # Fallback si no hay columna fecha
            ultima_fecha = None

        # --- FASE 4: KPIS DERIVADOS (UNITARIOS) ---
        # Usamos np.where o replace para evitar divisiones por cero (infinito)
        if 'VALOR US$ CIF' in df.columns and 'CANTIDAD' in df.columns:
            df['CIF_UNITARIO'] = (df['VALOR US$ CIF'] / df['CANTIDAD']).replace([np.inf, -np.inf], 0).fillna(0)
            
        if 'FLETE' in df.columns and 'CANTIDAD' in df.columns:
            df['FLETE_UNITARIO'] = (df['FLETE'] / df['CANTIDAD']).replace([np.inf, -np.inf], 0).fillna(0)
            
        return df, ultima_fecha
        
    except Exception as e:
        # Log del error en consola para debugging
        print(f"Error ETL: {e}")
        st.error(f"Error crítico cargando la base de datos: {str(e)}")
        return None, None

def aplicar_logica_temporal(df, ultima_fecha):
    """
    Aplica el filtro de visión temporal seleccionado por el usuario.
    
    Lógica YTD (Year To Date):
    Si la base de datos termina en Agosto 2024, el sistema recortará
    automáticamente los datos de 2023, 2022, etc., para mostrar solo
    hasta Agosto de cada año. Esto permite comparaciones "peras con peras".
    """
    if st.session_state['time_view'] == 'YTD (Year to Date)' and ultima_fecha:
        mes_corte = ultima_fecha.month
        # Filtramos para que todos los años terminen en el mes de corte actual
        df_filtrado = df[df['MES_NUM'] <= mes_corte].copy()
        return df_filtrado
    
    # Si es Full Year, devolvemos todo sin cortar
    return df

# ==============================================================================
# ==============================================================================
# 4. MOTOR DE REPORTES PDF (CLASE FPDF OPTIMIZADA)
# ==============================================================================
# ==============================================================================

class ReportePDF(FPDF):
    """Clase extendida de FPDF para reportes corporativos"""
    
    def header(self):
        # Encabezado corporativo en cada página
        self.set_font('Arial', 'B', 14)
        self.set_text_color(30, 55, 153) # Azul oscuro
        self.cell(0, 10, 'Reporte de Inteligencia de Mercado - Automotriz', 0, 1, 'C')
        self.ln(5)
        
    def footer(self):
        # Pie de página con numeración y fecha
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        fecha_gen = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.cell(0, 10, f'Pag {self.page_no()} - Generado el {fecha_gen} | Confidencial', 0, 0, 'C')

def limpiar_texto_pdf(text):
    """
    Sanitiza cadenas de texto para evitar errores de codificación latin-1 en FPDF.
    Reemplaza caracteres no soportados.
    """
    try: 
        return str(text).encode('latin-1', 'replace').decode('latin-1')
    except: 
        return str(text)

@st.cache_data(show_spinner=False)
def generar_pdf_master(df_dict, titulo, subtitulo, view_mode):
    """
    Generador Maestro de PDFs. Toma un diccionario de datos (para cacheabilidad),
    y construye un reporte ejecutivo con resumen, tablas y rankings.
    """
    # Convertir dict a DataFrame (operación ligera)
    df = pd.DataFrame(df_dict)
    
    pdf = ReportePDF()
    pdf.add_page()
    
    # 1. BLOQUE DE TÍTULO Y CONTEXTO
    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(0) # Negro
    pdf.cell(0, 10, limpiar_texto_pdf(titulo), 0, 1, 'L')
    
    pdf.set_font("Arial", 'I', 11)
    pdf.set_text_color(100) # Gris
    pdf.cell(0, 10, f"Vista Temporal: {limpiar_texto_pdf(view_mode)} | {limpiar_texto_pdf(subtitulo)}", 0, 1, 'L')
    pdf.ln(5)
    
    # 2. BLOQUE DE RESUMEN EJECUTIVO (KPIs)
    # Cálculos agregados
    total_vol = df['CANTIDAD'].sum()
    total_val = df['VALOR US$ CIF'].sum()
    promedio = total_val / total_vol if total_vol else 0
    
    # Dibujar caja de fondo gris
    pdf.set_fill_color(245, 245, 245)
    pdf.set_draw_color(220, 220, 220)
    pdf.rect(10, 45, 190, 25, 'FD')
    
    # Textos de KPIs
    pdf.set_y(52)
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(0)
    
    # Distribución en 3 columnas
    pdf.cell(63, 10, f"Volumen Total: {total_vol:,.0f}", 0, 0, 'C')
    pdf.cell(63, 10, f"Inversion CIF: ${total_val/1e6:,.1f} M", 0, 0, 'C')
    pdf.cell(63, 10, f"Ticket Prom: ${promedio:,.0f}", 0, 1, 'C')
    pdf.ln(25)

    # 3. BLOQUE DE TABLA PRINCIPAL (TOP 15)
    pdf.set_font("Arial", 'B', 13)
    pdf.set_text_color(30, 55, 153)
    
    # Determinar dinámicamente el agrupador más relevante
    if 'MODELO' in df.columns and len(df['MODELO'].unique()) > 1:
        agrupador = 'MODELO'
    elif 'MARCA' in df.columns:
        agrupador = 'MARCA'
    else:
        agrupador = 'AÑO'

    pdf.cell(0, 10, f"Ranking Top 15 - Desglose por {limpiar_texto_pdf(agrupador)}", 0, 1)
    pdf.ln(2)
    
    # Encabezados de Tabla
    pdf.set_font("Arial", 'B', 10)
    pdf.set_text_color(255) # Blanco
    pdf.set_fill_color(44, 62, 80) # Azul oscuro fondo
    
    pdf.cell(140, 8, limpiar_texto_pdf(agrupador), 1, 0, 'L', 1)
    pdf.cell(50, 8, "Volumen (Unds)", 1, 1, 'R', 1)
    
    # Cuerpo de Tabla
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(0) # Negro
    
    top_data = df.groupby(agrupador)['CANTIDAD'].sum().sort_values(ascending=False).head(15)
    
    fill = False # Alternancia de colores en filas
    for nombre, val in top_data.items():
        if fill: pdf.set_fill_color(240, 240, 240)
        else: pdf.set_fill_color(255, 255, 255)
        
        pdf.cell(140, 8, limpiar_texto_pdf(str(nombre))[:60], 1, 0, 'L', fill)
        pdf.cell(50, 8, f"{val:,.0f}", 1, 1, 'R', fill)
        fill = not fill # Alternar
        
    pdf.ln(8)
    
    # 4. BLOQUE SECUNDARIO (IMPORTADORES)
    # Solo se muestra si existen datos de la empresa importadora
    if 'EMPRESA' in df.columns:
        pdf.set_font("Arial", 'B', 13)
        pdf.set_text_color(30, 55, 153)
        pdf.cell(0, 10, "Top 5 Importadores Clave Detectados", 0, 1)
        
        pdf.set_font("Arial", '', 10)
        pdf.set_text_color(0)
        
        top_imp = df.groupby('EMPRESA')['CANTIDAD'].sum().sort_values(ascending=False).head(5)
        for nombre, val in top_imp.items():
            pdf.cell(140, 7, f"- {limpiar_texto_pdf(str(nombre))[:65]}", 0, 0, 'L')
            pdf.cell(50, 7, f"{val:,.0f}", 0, 1, 'R')

    return pdf.output(dest='S').encode('latin-1')

# ==============================================================================
# ==============================================================================
# 5. INTERFAZ DE USUARIO (SIDEBAR & MAIN)
# ==============================================================================
# ==============================================================================

# Carga inicial de datos
df_raw, ultima_fecha_raw = cargar_datos_robusto()

# --- BARRA LATERAL (CONTROL CENTER) ---
with st.sidebar:
    st.title("🧠 Market Suite")
    st.caption("v26.0 | Enterprise Edition")
    
    if df_raw is not None:
        # A. STATUS DE DATOS
        st.success("✅ Conexión Establecida")
        
        if ultima_fecha_raw:
            str_fecha = ultima_fecha_raw.strftime("%d-%b-%Y")
            st.info(f"📅 **Data actualizada al:**\n\n{str_fecha}")
        
        st.divider()

        # B. CONTROLES DE VISUALIZACIÓN
        st.subheader("⚙️ Preferencias")
        
        # Selector de Tema
        c_theme1, c_theme2 = st.columns(2)
        with c_theme1:
            if st.button("🌙 Dark", use_container_width=True): 
                st.session_state['theme_mode'] = 'Dark Force'
                st.rerun()
        with c_theme2:
            if st.button("☀️ Light", use_container_width=True): 
                st.session_state['theme_mode'] = 'Light Force'
                st.rerun()
            
        # Selector de Tiempo (Fundamental para análisis YoY)
        st.markdown("**Visión Temporal:**")
        time_mode = st.radio("Corte de Datos:", 
                             ["Full Year (Completo)", "YTD (Year to Date)"], 
                             index=0 if st.session_state['time_view']=='Full Year' else 1,
                             label_visibility="collapsed")
        
        # Detectar cambio y recargar si es necesario
        if time_mode != st.session_state['time_view']:
            st.session_state['time_view'] = time_mode
            st.rerun()
        
        st.divider()
        
        # C. NAVEGACIÓN PRINCIPAL
        st.subheader("📍 Módulos")
        menu = st.radio("Ir a:", 
                        ["🌍 1. Visión País (Macro)", 
                         "⚔️ 2. Guerra de Marcas (Benchmark)", 
                         "🔍 3. Auditoría de Marca (Deep Dive)"], label_visibility="collapsed")
        st.divider()
        
    else:
        st.error("⚠️ Error Crítico: No se encuentra el archivo 'historial_lite.parquet'.")
        st.stop()

# ==============================================================================
# 6. LÓGICA DE NEGOCIO POR MÓDULO
# ==============================================================================

# Aplicar filtro temporal global
df_main = aplicar_logica_temporal(df_raw, ultima_fecha_raw)

# Variables contenedoras para la exportación PDF final
pdf_dataset = pd.DataFrame()
pdf_title = ""

# ------------------------------------------------------------------------------
# MÓDULO 1: VISIÓN PAÍS (MACROANALYSIS)
# ------------------------------------------------------------------------------
if menu == "🌍 1. Visión País (Macro)":
    st.title(f"🌍 Visión País: {st.session_state['time_view']}")
    st.markdown("Análisis macroeconómico de importaciones automotrices.")
    
    # Selector de Años
    years_avail = sorted(df_main['AÑO'].unique(), reverse=True)
    sel_years = st.multiselect("Periodo de Análisis", years_avail, default=years_avail[:2])
    
    # Filtrado Local
    df_view = df_main[df_main['AÑO'].isin(sel_years)].copy()
    
    # --- SECCIÓN A: KPIS GENERALES ---
    vol_actual = df_view['CANTIDAD'].sum()
    val_actual = df_view['VALOR US$ CIF'].sum()
    
    with st.container():
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Volumen Total", f"{vol_actual:,.0f}", delta="Unidades Importadas")
        k2.metric("Inversión CIF", f"${val_actual/1e6:,.1f} M", delta="Millones USD")
        k3.metric("Ticket Promedio", f"${(val_actual/vol_actual if vol_actual else 0):,.0f}", delta="Costo Unitario")
        k4.metric("Marcas Activas", f"{df_view['MARCA'].nunique()}", delta="Competidores")

    st.markdown("---")

    # --- SECCIÓN B: GRÁFICOS ESTRATÉGICOS ---
    col_a, col_b = st.columns([2, 1])
    
    with col_a:
        st.subheader("📈 Ritmo de Importación (Serie de Tiempo)")
        # Agrupación Mensual
        mensual = df_view.groupby(['AÑO', 'MES_NUM'])['CANTIDAD'].sum().reset_index()
        # Crear fecha artificial día 1 para que el eje X sea temporal
        mensual['Fecha'] = pd.to_datetime(mensual['AÑO'].astype(str) + '-' + mensual['MES_NUM'].astype(str) + '-01')
        
        fig_line = px.line(mensual, x='Fecha', y='CANTIDAD', markers=True, color='AÑO', 
                          labels={'CANTIDAD':'Unidades', 'Fecha':'Mes de Registro'})
        fig_line.update_layout(xaxis_title=None, legend_title="Año Fiscal")
        st.plotly_chart(fig_line, use_container_width=True)
        
    with col_b:
        st.subheader("⚡ Mix Energético")
        fig_pie = px.pie(df_view, values='CANTIDAD', names='COMBUSTIBLE', hole=0.4,
                         color_discrete_sequence=px.colors.qualitative.Prism)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

    col_c, col_d = st.columns(2)
    with col_c:
        st.subheader("💰 Segmentación de Precios")
        # Definición de rangos de precio (Bins)
        bins = [0, 15000, 25000, 40000, 70000, 1000000]
        labels = ['Económico (<15k)', 'Masivo (15-25k)', 'Medio (25-40k)', 'Premium (40-70k)', 'Lujo (>70k)']
        
        df_view['SEGMENTO'] = pd.cut(df_view['CIF_UNITARIO'], bins=bins, labels=labels)
        seg = df_view.groupby('SEGMENTO', observed=True)['CANTIDAD'].sum().reset_index()
        
        fig_seg = px.bar(seg, x='CANTIDAD', y='SEGMENTO', orientation='h', color='SEGMENTO', text_auto=True)
        fig_seg.update_layout(showlegend=False, xaxis_title="Unidades")
        st.plotly_chart(fig_seg, use_container_width=True)

    with col_d:
        st.subheader("🏆 Market Share Acumulado")
        # Tabla simple de top 15
        top = df_view.groupby('MARCA')['CANTIDAD'].sum().sort_values(ascending=False).head(15).reset_index()
        top['Share'] = (top['CANTIDAD'] / top['CANTIDAD'].sum()) * 100
        
        # Usamos Native Column Config para barras de progreso
        st.dataframe(
            top,
            column_config={
                "CANTIDAD": st.column_config.ProgressColumn("Volumen", format="%d", min_value=0, max_value=top['CANTIDAD'].max()),
                "Share": st.column_config.NumberColumn("Part. %", format="%.1f%%")
            },
            hide_index=True,
            use_container_width=True
        )

    # --- SECCIÓN C: ANÁLISIS YoY (YEAR OVER YEAR) AVANZADO ---
    st.markdown("---")
    st.subheader("📊 Análisis de Crecimiento Anual (YoY)")
    st.info("💡 Este panel compara el rendimiento del Año Actual vs el Año Anterior seleccionado.")

    # Selectores dinámicos
    dim_col = st.radio("Dimensión de Análisis:", ["MARCA", "MODELO", "COMBUSTIBLE", "CARROCERIA"], horizontal=True)
    
    # Lógica Matemática YoY
    if len(sel_years) >= 2:
        curr_y = max(sel_years)
        prev_y = curr_y - 1 # Asumimos comparación con n-1
        
        # Dataframes separados
        df_curr = df_view[df_view['AÑO'] == curr_y]
        df_prev = df_main[df_main['AÑO'] == prev_y] # Usamos df_main para tener contexto completo del año anterior
        
        # Agrupaciones
        grp_curr = df_curr.groupby(dim_col).agg(Vol_Actual=('CANTIDAD','sum'), CIF_Actual=('VALOR US$ CIF','sum')).reset_index()
        grp_prev = df_prev.groupby(dim_col).agg(Vol_Prev=('CANTIDAD','sum'), CIF_Prev=('VALOR US$ CIF','sum')).reset_index()
        
        # Cálculo de Share relativo a su propio año
        grp_curr['Share_Actual'] = (grp_curr['Vol_Actual'] / grp_curr['Vol_Actual'].sum()) * 100
        grp_prev['Share_Prev'] = (grp_prev['Vol_Prev'] / grp_prev['Vol_Prev'].sum()) * 100
        
        # Fusión de datos (Outer join para no perder marcas que existían antes y ahora no, o viceversa)
        df_yoy = pd.merge(grp_curr, grp_prev, on=dim_col, how='outer').fillna(0)
        
        # Cálculo de Deltas (Variaciones)
        df_yoy['Δ Share (pp)'] = df_yoy['Share_Actual'] - df_yoy['Share_Prev']
        df_yoy['Δ Inversión ($)'] = df_yoy['CIF_Actual'] - df_yoy['CIF_Prev']
        
        # Crear columnas visuales de estado
        df_yoy['Estado'] = np.where(df_yoy['Δ Share (pp)'] >= 0, '🟢 Ganó', '🔻 Perdió')

        # --- SOLUCIÓN AL ERROR DE MATPLOTLIB ---
        # En lugar de usar .style.background_gradient (que requiere matplotlib),
        # usamos st.column_config para formatear visualmente la tabla de forma nativa.
        
        st.dataframe(
            df_yoy.sort_values('Vol_Actual', ascending=False).head(50),
            column_config={
                dim_col: st.column_config.TextColumn("Categoría", width="medium"),
                "Vol_Actual": st.column_config.NumberColumn("Vol '24", format="%d"),
                "Vol_Prev": st.column_config.NumberColumn("Vol '23", format="%d"),
                "Share_Actual": st.column_config.ProgressColumn("Share Actual", format="%.1f%%", min_value=0, max_value=30),
                "Δ Share (pp)": st.column_config.NumberColumn("Var Share", format="%+.1f pp"), # El + fuerza el signo
                "Δ Inversión ($)": st.column_config.NumberColumn("Var Inversión", format="$%d"),
                "Estado": st.column_config.TextColumn("Tendencia")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.warning("⚠️ Selecciona al menos 2 años (ej: 2024 y 2023) para habilitar el cálculo de crecimiento.")

    # Preparar datos para PDF
    pdf_dataset = df_view
    pdf_title = "Reporte Macro Pais"


# ------------------------------------------------------------------------------
# MÓDULO 2: BENCHMARK (GUERRA DE MARCAS)
# ------------------------------------------------------------------------------
elif menu == "⚔️ 2. Guerra de Marcas (Benchmark)":
    st.title(f"⚔️ Benchmarking Competitivo: {st.session_state['time_view']}")
    
    with st.sidebar:
        st.markdown("### 🎯 Selección de Rivales")
        years_avail = sorted(df_main['AÑO'].unique(), reverse=True)
        sel_years = st.multiselect("Años a Comparar", years_avail, default=years_avail[:1])
        df_curr = df_main[df_main['AÑO'].isin(sel_years)]
        
        # Selector inteligente de marcas
        all_brands = sorted(df_curr['MARCA'].unique())
        if st.checkbox("Seleccionar Todas las Marcas", value=False):
            sel_brands = all_brands
        else:
            default_top = df_curr['MARCA'].value_counts().head(3).index.tolist()
            sel_brands = st.multiselect("Marcas", all_brands, default=default_top)

    df_view = df_curr[df_curr['MARCA'].isin(sel_brands)].copy()
    
    if not df_view.empty:
        # Pestañas de Análisis
        t1, t2, t3 = st.tabs(["📊 Volumen & Mix", "💰 Precios", "🕵️ Auditoría Gris"])
        
        with t1:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("6. Batalla de Volumen")
                st.plotly_chart(px.bar(df_view, x='MARCA', y='CANTIDAD', color='AÑO', barmode='group'), use_container_width=True)
            with c2:
                # GRÁFICO NUEVO SOLICITADO: MIX DE COMBUSTIBLE POR MARCA
                st.subheader("9. Estrategia de Motorización")
                st.plotly_chart(px.bar(df_view, x='MARCA', y='CANTIDAD', color='COMBUSTIBLE', title="Mix: Eléctrico vs Combustión"), use_container_width=True)

        with t2:
            st.subheader("7. Matriz de Precios")
            # Filtro visual para evitar distorsión por errores de data
            df_p = df_view[(df_view['CIF_UNITARIO'] > 2000) & (df_view['CIF_UNITARIO'] < 150000)]
            
            fig_box = px.box(df_p, x='MARCA', y='CIF_UNITARIO', color='MARCA', points="outliers")
            fig_box.update_layout(showlegend=False)
            st.plotly_chart(fig_box, use_container_width=True)
            st.caption("Cajas alargadas indican un portafolio de precios amplio. Cajas pequeñas indican nicho.")

        with t3:
            st.subheader("8. Auditoría de Fuga (Oficial vs Paralelo)")
            
            # Algoritmo de Detección de Oficiales
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
                                       title="Volumen Absoluto", 
                                       color_discrete_map={'OFICIAL':'#27ae60', 'GRIS':'#95a5a6'}), use_container_width=True)
            with c_g2:
                # GRÁFICO NUEVO SOLICITADO: RANKING DE % DE FUGA
                if 'GRIS' in resumen.columns:
                    resumen['Total'] = resumen['OFICIAL'] + resumen['GRIS']
                    resumen['% Fuga'] = (resumen['GRIS'] / resumen['Total']) * 100
                    
                    fig_pct = px.bar(resumen, x='MARCA', y='% Fuga', title="Ranking de Vulnerabilidad (% Fuga)", 
                                     text_auto='.1f', color='% Fuga', color_continuous_scale='Reds')
                    st.plotly_chart(fig_pct, use_container_width=True)
                else:
                    st.success("No se detectó fuga relevante en las marcas seleccionadas.")
            
            st.markdown("**Identidad del Distribuidor Oficial Detectado:**")
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
        # Panel de KPIs
        with st.container():
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Volumen", f"{df_view['CANTIDAD'].sum():,.0f}")
            k2.metric("CIF Promedio", f"${df_view['CIF_UNITARIO'].mean():,.0f}")
            k3.metric("Flete Promedio", f"${df_view['FLETE_UNITARIO'].mean():,.0f}")
            k4.metric("Modelos Activos", f"{df_view['MODELO'].nunique()}")
        
        tab_a, tab_b, tab_c = st.tabs(["Eficiencia (Pareto)", "Futuro (Forecast)", "Logística"])
        
        with tab_a:
            # 11. ANÁLISIS DE PARETO
            st.subheader("11. Eficiencia de Portafolio")
            pareto = df_view.groupby('MODELO')['CANTIDAD'].sum().sort_values(ascending=False).reset_index()
            pareto['% Acum'] = (pareto['CANTIDAD'].cumsum() / pareto['CANTIDAD'].sum()) * 100
            pareto['Clasificación'] = np.where(pareto['% Acum'] <= 80, 'A (Vital)', 'B (Cola)')
            
            fig_p = px.bar(pareto, x='MODELO', y='CANTIDAD', color='Clasificación', 
                           color_discrete_map={'A (Vital)': '#27ae60', 'B (Cola)': '#95a5a6'})
            st.plotly_chart(fig_p, use_container_width=True)
            
        with tab_b:
            c_f1, c_f2 = st.columns(2)
            with c_f1:
                # 12. FORECAST
                st.subheader("12. Proyección de Tendencia")
                mensual = df_view.groupby('MES_NUM')['CANTIDAD'].sum().reset_index()
                mensual['Fecha'] = pd.to_datetime(str(y_dd) + '-' + mensual['MES_NUM'].astype(str) + '-01')
                
                try:
                    # Intento de regresión lineal (OLS)
                    fig_tr = px.scatter(mensual, x='Fecha', y='CANTIDAD', trendline="ols", trendline_color_override="red")
                    fig_tr.update_traces(mode='lines+markers')
                    st.plotly_chart(fig_tr, use_container_width=True)
                except:
                    # Fallback si hay pocos datos
                    st.line_chart(mensual.set_index('Fecha')['CANTIDAD'])

            with c_f2:
                # 14. TICKET EVOLUTION
                st.subheader("14. Evolución de Precio (Ticket)")
                evol_precio = df_view.groupby('MES_NUM')['CIF_UNITARIO'].mean().reset_index()
                evol_precio['Fecha'] = pd.to_datetime(str(y_dd) + '-' + evol_precio['MES_NUM'].astype(str) + '-01')
                st.plotly_chart(px.line(evol_precio, x='Fecha', y='CIF_UNITARIO', markers=True), use_container_width=True)

        with tab_c:
            c_l1, c_l2 = st.columns(2)
            with c_l1:
                # 13. SEMÁFORO LOGÍSTICO
                st.subheader("13. Costos Logísticos")
                fletes = df_view[(df_view['FLETE_UNITARIO'] > 50) & (df_view['FLETE_UNITARIO'] < 8000)]
                if not fletes.empty:
                    st.plotly_chart(px.box(fletes, y='FLETE_UNITARIO', title="Dispersión Flete Unitario"), use_container_width=True)
                else:
                    st.info("Sin datos de fletes válidos.")
            
            with c_l2:
                # 15. ESTACIONALIDAD (CORRECCIÓN DEL ERROR DE IMPORT)
                st.subheader("15. Mapa de Calor Estacional")
                
                # Preparamos datos para Heatmap de Plotly (Nativo, no usa Matplotlib)
                heatmap_data = df_view.groupby('MES_NUM')['CANTIDAD'].sum().reset_index()
                heatmap_data['Nombre_Mes'] = heatmap_data['MES_NUM'].apply(lambda x: calendar.month_abbr[x])
                
                # Creamos Heatmap interactivo
                fig_heat = px.density_heatmap(
                    heatmap_data, 
                    x="Nombre_Mes", 
                    y="CANTIDAD", 
                    nbinsx=12, 
                    title="Intensidad de Importación por Mes", 
                    color_continuous_scale="Blues"
                )
                st.plotly_chart(fig_heat, use_container_width=True)

    pdf_dataset = df_view
    pdf_title = f"Auditoria {brand_dd} ({y_dd})"

# ==============================================================================
# ==============================================================================
# 7. EXPORTACIÓN PDF (BOTÓN FINAL)
# ==============================================================================
# ==============================================================================

if 'pdf_dataset' in locals() and not pdf_dataset.empty:
    st.sidebar.divider()
    st.sidebar.markdown("### 📥 Exportar Reporte")
    
    try:
        # Optimización: Serialización ligera a Dict para el caché
        data_dict = pdf_dataset.to_dict(orient='list')
        
        # Generación PDF en Background
        pdf_bytes = generar_pdf_master(
            data_dict, 
            pdf_title, 
            f"Modo: {st.session_state['time_view']}", 
            st.session_state['time_view']
        )
        
        # Botón de Descarga
        st.sidebar.download_button(
            label="💾 Descargar PDF Ejecutivo",
            data=pdf_bytes,
            file_name=f"Reporte_{pdf_title.replace(' ','_')}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.sidebar.warning(f"Error generando PDF: {e}")

# Limpieza final de memoria
gc.collect()

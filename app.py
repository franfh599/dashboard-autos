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
# 1. CONFIGURACIÓN Y ESTADO INICIAL
# ==============================================================================
st.set_page_config(
    page_title="EV Market Intelligence Suite", 
    layout="wide", 
    page_icon="🧠",
    initial_sidebar_state="expanded"
)

# Inicialización de Session State para controles globales
if 'theme_mode' not in st.session_state:
    st.session_state['theme_mode'] = 'System'
if 'time_view' not in st.session_state:
    st.session_state['time_view'] = 'Full Year' # Opciones: Full Year, YTD

# ==============================================================================
# 2. GESTIÓN DE TEMAS Y ESTILOS (CSS AVANZADO)
# ==============================================================================
def inject_custom_css():
    """
    Inyecta CSS dinámico basado en la selección del usuario.
    Permite que los menús y tablas reaccionen al cambio de tema.
    """
    # Colores base
    color_primary = "#1e3799"
    
    # CSS Base para PDF y Contenedores
    base_css = """
    <style>
        .block-container {padding-top: 1rem; padding-bottom: 5rem;}
        
        /* Ajuste de Tabs para que se vean bien en cualquier fondo */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            border-bottom: 1px solid #ddd;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            border-radius: 4px 4px 0px 0px;
            padding: 10px 20px;
        }
        
        /* Tarjetas de Métricas (KPIs) Adaptativas */
        div[data-testid="stMetric"] {
            background-color: rgba(255, 255, 255, 0.05); /* Transparencia sutil */
            border: 1px solid rgba(128, 128, 128, 0.2);
            padding: 15px;
            border-radius: 8px;
            border-left: 5px solid #1e3799;
        }
    </style>
    """
    st.markdown(base_css, unsafe_allow_html=True)

    # Lógica de Cambio de Tema (Hack CSS para forzar inversión de colores si se solicita)
    if st.session_state['theme_mode'] == 'Dark Force':
        st.markdown("""
        <style>
            .stApp {
                background-color: #0e1117;
                color: #fafafa;
            }
            .stDataFrame { filter: invert(0); } /* Tablas nativas */
        </style>
        """, unsafe_allow_html=True)
    elif st.session_state['theme_mode'] == 'Light Force':
        st.markdown("""
        <style>
            .stApp {
                background-color: #ffffff;
                color: #000000;
            }
        </style>
        """, unsafe_allow_html=True)

inject_custom_css()

# ==============================================================================
# 3. MOTOR DE INTELIGENCIA DE DATOS (BACKEND)
# ==============================================================================

@st.cache_data(show_spinner=False)
def cargar_datos_robusto():
    """
    Carga, limpia y enriquece los datos. 
    Calcula la 'Última Fecha' y prepara columnas derivadas.
    """
    archivo = "historial_lite.parquet"
    if not os.path.exists(archivo): return None, None
    
    try:
        df = pd.read_parquet(archivo)
        df.columns = df.columns.str.strip().str.upper()
        
        # 1. Normalización de Cadenas (Vectorizada)
        cols_txt = ['MARCA', 'MODELO', 'EMPRESA', 'COMBUSTIBLE', 'CARROCERIA', 'MES']
        for c in cols_txt:
            if c in df.columns: 
                df[c] = df[c].astype(str).str.strip().str.upper()
        
        # Corrección de Nombres Clave
        if 'MARCA' in df.columns:
            df['MARCA'] = df['MARCA'].replace({
                'M.G.': 'MG', 'MORRIS GARAGES': 'MG', 'M. G.': 'MG',
                'BYD AUTO': 'BYD', 'TOYOTA MOTOR': 'TOYOTA'
            })
            
        # 2. Conversión Numérica
        for c in ['CANTIDAD', 'VALOR US$ CIF', 'FLETE']:
            if c in df.columns: 
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
                
        # 3. Ingeniería de Fechas (CRÍTICO)
        if 'FECHA' in df.columns:
            df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
            df = df.dropna(subset=['FECHA'])
            df['AÑO'] = df['FECHA'].dt.year.astype(int)
            df['MES_NUM'] = df['FECHA'].dt.month.astype(int)
            
            # Obtener última fecha reportada
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
        st.error(f"Error crítico en base de datos: {e}")
        return None, None

def aplicar_logica_ytd(df, ultima_fecha):
    """
    Filtra el DataFrame para análisis Year-To-Date.
    Si estamos en Agosto 2024, corta todos los años anteriores en Agosto.
    """
    if st.session_state['time_view'] == 'YTD (Year to Date)' and ultima_fecha:
        mes_corte = ultima_fecha.month
        dia_corte = ultima_fecha.day
        
        # Filtramos meses
        df_ytd = df[df['MES_NUM'] <= mes_corte].copy()
        
        # Opcional: Filtro fino de días si se requiere extrema precisión
        # df_ytd = df_ytd[df_ytd['FECHA'].dt.day <= dia_corte] 
        return df_ytd
    
    return df

# ==============================================================================
# 4. MOTOR DE REPORTE PDF (EJECUTIVO & ROBUSTO)
# ==============================================================================
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Reporte de Inteligencia de Mercado Automotriz', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()} - Generado el {datetime.now().strftime("%Y-%m-%d")}', 0, 0, 'C')

def clean_text(text):
    """Sanea texto para evitar crashes de codificación Latin-1"""
    try: return str(text).encode('latin-1', 'replace').decode('latin-1')
    except: return str(text)

@st.cache_data(show_spinner=False)
def generar_pdf_master(df_dict, titulo, subtitulo, view_mode):
    # Reconstrucción de DataFrame
    df = pd.DataFrame(df_dict)
    
    pdf = PDF()
    pdf.add_page()
    
    # 1. TÍTULO Y CONTEXTO
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, clean_text(titulo), 0, 1, 'L')
    pdf.set_font("Arial", 'I', 11)
    pdf.cell(0, 10, f"Vista: {clean_text(view_mode)} | {clean_text(subtitulo)}", 0, 1, 'L')
    pdf.ln(5)
    
    # 2. RESUMEN EJECUTIVO (KPIs)
    total_vol = df['CANTIDAD'].sum()
    total_val = df['VALOR US$ CIF'].sum()
    promedio = total_val / total_vol if total_vol else 0
    
    # Caja Gris de Resumen
    pdf.set_fill_color(240, 240, 240)
    pdf.rect(10, 45, 190, 20, 'F')
    pdf.set_y(50)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(63, 10, f"Volumen: {total_vol:,.0f}", 0, 0, 'C')
    pdf.cell(63, 10, f"Inversion: ${total_val/1e6:,.1f} M", 0, 0, 'C')
    pdf.cell(63, 10, f"Ticket Prom: ${promedio:,.0f}", 0, 1, 'C')
    pdf.ln(15)

    # 3. TABLA PRINCIPAL (Dinámica)
    pdf.set_font("Arial", 'B', 12)
    agrupador = 'MODELO' if 'MODELO' in df.columns and len(df['MODELO'].unique()) > 1 else 'MARCA'
    pdf.cell(0, 10, f"Top 15 {clean_text(agrupador)} por Volumen", 0, 1)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(200, 200, 200)
    pdf.cell(140, 8, clean_text(agrupador), 1, 0, 'L', 1)
    pdf.cell(50, 8, "Unidades", 1, 1, 'R', 1)
    
    pdf.set_font("Arial", '', 10)
    top_data = df.groupby(agrupador)['CANTIDAD'].sum().sort_values(ascending=False).head(15)
    
    for nombre, val in top_data.items():
        pdf.cell(140, 8, clean_text(str(nombre))[:60], 1)
        pdf.cell(50, 8, f"{val:,.0f}", 1, 1, 'R')
    pdf.ln(5)
    
    # 4. TABLA SECUNDARIA (Importadores)
    if 'EMPRESA' in df.columns:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Top 5 Importadores", 0, 1)
        pdf.set_font("Arial", '', 10)
        top_imp = df.groupby('EMPRESA')['CANTIDAD'].sum().sort_values(ascending=False).head(5)
        for nombre, val in top_imp.items():
            pdf.cell(140, 8, clean_text(str(nombre))[:60], 1)
            pdf.cell(50, 8, f"{val:,.0f}", 1, 1, 'R')

    return pdf.output(dest='S').encode('latin-1')

# ==============================================================================
# 5. CARGA E INTERFAZ DE BARRA LATERAL
# ==============================================================================
df_raw, ultima_fecha_raw = cargar_datos_robusto()

with st.sidebar:
    st.title("🧠 Market Suite")
    
    if df_raw is not None:
        # A. CONTROL DE ESTADO DE DATOS
        st.success("✅ Sistema Online")
        
        # B. INFORMACIÓN DE ÚLTIMA ACTUALIZACIÓN (Requerimiento Clave)
        if ultima_fecha_raw:
            str_fecha = ultima_fecha_raw.strftime("%d-%b-%Y")
            st.metric("📅 Datos actualizados al:", str_fecha)
        
        st.divider()

        # C. CONTROLES DE TEMA Y TIEMPO (Requerimiento Clave)
        st.subheader("⚙️ Configuración")
        
        # Toggle de Tema
        c_theme1, c_theme2 = st.columns(2)
        with c_theme1:
            if st.button("🌙 Dark"): st.session_state['theme_mode'] = 'Dark Force'
        with c_theme2:
            if st.button("☀️ Light"): st.session_state['theme_mode'] = 'Light Force'
            
        # Toggle de Tiempo (YOY / YTD)
        time_mode = st.radio("Visión Temporal:", ["Full Year (Completo)", "YTD (Year to Date)"])
        st.session_state['time_view'] = time_mode
        
        st.divider()
        
        # D. NAVEGACIÓN ESTRATÉGICA
        menu = st.radio("Módulo de Análisis:", 
                        ["🌍 1. Visión País (Macro)", 
                         "⚔️ 2. Guerra de Marcas (Benchmark)", 
                         "🔍 3. Auditoría de Marca (Deep Dive)"])
        st.divider()
        
    else:
        st.error("⚠️ Error Crítico: No se encuentran los datos.")
        st.stop()

# ==============================================================================
# 6. PROCESAMIENTO DE DATOS (FILTRO GLOBAL)
# ==============================================================================

# Aplicar lógica YTD Globalmente si está seleccionada
df_main = aplicar_logica_ytd(df_raw, ultima_fecha_raw)

# Variables para exportación PDF
pdf_dataset = pd.DataFrame()
pdf_title = ""

# ==============================================================================
# 7. MÓDULOS DE ANÁLISIS
# ==============================================================================

if menu == "🌍 1. Visión País (Macro)":
    st.title(f"🌍 Visión País: {st.session_state['time_view']}")
    
    # Filtros
    years_avail = sorted(df_main['AÑO'].unique(), reverse=True)
    sel_years = st.multiselect("Periodo", years_avail, default=years_avail[:2])
    df_view = df_main[df_main['AÑO'].isin(sel_years)].copy()
    
    # --- HERRAMIENTAS 1-5 ---
    
    # 1. TERMÓMETRO DE MERCADO (KPIs con Delta)
    # Calculamos Delta (Variación vs año anterior si hay 2 años seleccionados)
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

    with col_d:
        # 5. ÍNDICE DE CONCENTRACIÓN (Market Share)
        st.subheader("🏆 Market Share Acumulado")
        share = df_view.groupby('MARCA')['CANTIDAD'].sum().sort_values(ascending=False).head(15).reset_index()
        share['Share %'] = (share['CANTIDAD'] / share['CANTIDAD'].sum()) * 100
        st.dataframe(share.style.format({'Share %': '{:.1f}%'}), use_container_width=True, hide_index=True)

    pdf_dataset = df_view
    pdf_title = "Reporte Macro Pais"


elif menu == "⚔️ 2. Guerra de Marcas (Benchmark)":
    st.title(f"⚔️ Benchmarking Competitivo: {st.session_state['time_view']}")
    
    with st.sidebar:
        st.markdown("### 🎯 Competidores")
        years_avail = sorted(df_main['AÑO'].unique(), reverse=True)
        sel_years = st.multiselect("Años a Comparar", years_avail, default=years_avail[:1])
        df_curr = df_main[df_main['AÑO'].isin(sel_years)]
        
        all_brands = sorted(df_curr['MARCA'].unique())
        if st.checkbox("Seleccionar Todos", value=False):
            sel_brands = all_brands
        else:
            default_top = df_curr['MARCA'].value_counts().head(3).index.tolist()
            sel_brands = st.multiselect("Marcas", all_brands, default=default_top)

    df_view = df_curr[df_curr['MARCA'].isin(sel_brands)].copy()
    
    if not df_view.empty:
        # TABS PARA ORGANIZAR LAS HERRAMIENTAS
        t1, t2, t3 = st.tabs(["Volumen & Producto", "Precios", "Auditoría Gris"])
        
        with t1:
            c1, c2 = st.columns(2)
            with c1:
                # 6. BATALLA DE VOLUMEN
                st.subheader("📊 Comparativo Volumen")
                st.plotly_chart(px.bar(df_view, x='MARCA', y='CANTIDAD', color='AÑO', barmode='group'), use_container_width=True)
            with c2:
                # 9. MIX DE PRODUCTO (Carrocería)
                st.subheader("🚙 Estrategia de Producto")
                st.plotly_chart(px.sunburst(df_view, path=['MARCA', 'CARROCERIA'], values='CANTIDAD'), use_container_width=True)

        with t2:
            # 7. MATRIZ DE ESTRATEGIA DE PRECIOS
            st.subheader("💸 Estrategia de Precios (Consistencia)")
            # Filtro de outliers visuales para el gráfico
            df_p = df_view[(df_view['CIF_UNITARIO'] > 2000) & (df_view['CIF_UNITARIO'] < 150000)]
            st.plotly_chart(px.box(df_p, x='MARCA', y='CIF_UNITARIO', color='MARCA', points="outliers"), use_container_width=True)
            st.info("💡 **Análisis:** Cajas compactas indican precios estandarizados. Cajas largas indican portafolio diverso (modelos baratos y caros).")

        with t3:
            # 8. AUDITORÍA MERCADO GRIS (ALGORITMO)
            st.subheader("🕵️ Detección de Fuga (Oficial vs Paralelo)")
            
            # Algoritmo Vectorizado de Detección
            # 1. Agrupar por Marca/Empresa
            gb = df_view.groupby(['MARCA', 'EMPRESA'])['CANTIDAD'].sum().reset_index()
            # 2. Identificar al mayor importador por marca
            lideres = gb.sort_values(['MARCA', 'CANTIDAD'], ascending=[True, False]).drop_duplicates('MARCA')
            lideres = lideres.rename(columns={'EMPRESA': 'LIDER_OFICIAL'})[['MARCA', 'LIDER_OFICIAL']]
            
            # 3. Cruzar datos
            df_view = df_view.merge(lideres, on='MARCA', how='left')
            df_view['CANAL'] = np.where(df_view['EMPRESA'] == df_view['LIDER_OFICIAL'], 'OFICIAL', 'GRIS')
            
            # Gráfico
            resumen = df_view.groupby(['MARCA', 'CANAL'])['CANTIDAD'].sum().unstack().fillna(0).reset_index()
            st.plotly_chart(px.bar(resumen, x='MARCA', y=[c for c in ['OFICIAL', 'GRIS'] if c in resumen.columns], 
                                   title="Volumen por Canal", color_discrete_map={'OFICIAL':'#27ae60', 'GRIS':'#95a5a6'}), use_container_width=True)
            
            # 10. RANKING DE IMPORTADORES REALES
            st.subheader("🏢 Identidad de Importadores Detectados")
            st.dataframe(lideres.set_index('MARCA'), use_container_width=True)

    pdf_dataset = df_view
    pdf_title = "Reporte Competitivo"


elif menu == "🔍 3. Auditoría de Marca (Deep Dive)":
    st.title(f"🔍 Auditoría Profunda: {st.session_state['time_view']}")
    
    with st.sidebar:
        st.markdown("### 🎯 Objetivo")
        y_dd = st.selectbox("Año Fiscal", sorted(df_main['AÑO'].unique(), reverse=True))
        df_y = df_main[df_main['AÑO'] == y_dd]
        
        brand_dd = st.selectbox("Marca a Auditar", sorted(df_y['MARCA'].unique()))
        df_view = df_y[df_y['MARCA'] == brand_dd].copy()

    if not df_view.empty:
        # KPIs DE MARCA
        with st.container(border=True):
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Volumen", f"{df_view['CANTIDAD'].sum():,.0f}")
            k2.metric("CIF Promedio", f"${df_view['CIF_UNITARIO'].mean():,.0f}")
            k3.metric("Flete Promedio", f"${df_view['FLETE_UNITARIO'].mean():,.0f}")
            k4.metric("Modelos Activos", f"{df_view['MODELO'].nunique()}")
        
        tab_a, tab_b, tab_c = st.tabs(["Eficiencia (Pareto)", "Proyección (Forecast)", "Logística"])
        
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
                # 12. FORECAST MATEMÁTICO (OLS)
                st.subheader("12. Proyección de Tendencia")
                mensual = df_view.groupby('MES_NUM')['CANTIDAD'].sum().reset_index()
                # Truco para graficar fechas correctamente
                mensual['Fecha'] = pd.to_datetime(str(y_dd) + '-' + mensual['MES_NUM'].astype(str) + '-01')
                
                if len(mensual) > 1:
                    try:
                        fig_tr = px.scatter(mensual, x='Fecha', y='CANTIDAD', trendline="ols", trendline_color_override="red")
                        fig_tr.update_traces(mode='lines+markers')
                        st.plotly_chart(fig_tr, use_container_width=True)
                    except:
                        st.line_chart(mensual.set_index('Fecha')['CANTIDAD'])
                else:
                    st.warning("Datos insuficientes para calcular tendencia matemática.")

            with c_f2:
                # 14. EVOLUCIÓN TICKET PROMEDIO
                st.subheader("14. Evolución de Costo (Ticket)")
                evol_precio = df_view.groupby('MES_NUM')['CIF_UNITARIO'].mean().reset_index()
                evol_precio['Fecha'] = pd.to_datetime(str(y_dd) + '-' + evol_precio['MES_NUM'].astype(str) + '-01')
                st.plotly_chart(px.line(evol_precio, x='Fecha', y='CIF_UNITARIO', markers=True), use_container_width=True)

        with tab_c:
            c_l1, c_l2 = st.columns(2)
            with c_l1:
                # 13. SEMÁFORO LOGÍSTICO (FLETES)
                st.subheader("13. Variabilidad Logística (Fletes)")
                fletes = df_view[(df_view['FLETE_UNITARIO'] > 50) & (df_view['FLETE_UNITARIO'] < 8000)]
                if not fletes.empty:
                    st.plotly_chart(px.box(fletes, y='FLETE_UNITARIO', title="Rango de Costo Flete"), use_container_width=True)
                else:
                    st.info("Sin datos de fletes válidos.")
            
            with c_l2:
                # 15. MAPA DE CALOR ESTACIONAL (Visualizado como Tabla Térmica)
                st.subheader("15. Estacionalidad Mensual")
                heatmap = df_view.groupby('MES_NUM')['CANTIDAD'].sum().reset_index().set_index('MES_NUM')
                st.dataframe(heatmap.style.background_gradient(cmap="Blues"), use_container_width=True)

    pdf_dataset = df_view
    pdf_title = f"Auditoria {brand_dd} ({y_dd})"


# ==============================================================================
# 8. EXPORTACIÓN PDF (BOTÓN SIEMPRE VISIBLE Y SEGURO)
# ==============================================================================
if 'pdf_dataset' in locals() and not pdf_dataset.empty:
    st.sidebar.divider()
    st.sidebar.markdown("### 📥 Exportar Reporte")
    
    # Botón directo sin estado intermedio para evitar el "Doble Click Error"
    try:
        # Convertimos a diccionario para que el Hashing de Streamlit sea instantáneo
        data_dict = pdf_dataset.to_dict(orient='list')
        
        # Generamos los bytes del PDF
        pdf_bytes = generar_pdf_master(
            data_dict, 
            pdf_title, 
            f"Modo: {st.session_state['time_view']}", 
            st.session_state['time_view']
        )
        
        st.sidebar.download_button(
            label="📄 Descargar PDF Ejecutivo",
            data=pdf_bytes,
            file_name=f"Reporte_{pdf_title.replace(' ','_')}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.sidebar.warning(f"No se pudo generar el PDF con esta selección de datos. Intenta filtrar menos registros.")

# Limpieza final de memoria
gc.collect()

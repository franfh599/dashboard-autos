import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import calendar
import os
import numpy as np
import gc
from fpdf import FPDF

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="EV Market Intelligence", 
    layout="wide", 
    page_icon="🧠",
    initial_sidebar_state="expanded"
)

# --- ESTILOS VISUALES PRO ---
st.markdown("""
<style>
    .main {background-color: #f8f9fa;}
    h1, h2, h3 {font-family: 'Helvetica', sans-serif; color: #2c3e50;}
    
    /* Tarjetas de KPIs */
    .kpi-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #3498db;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
    }
    
    /* Tabs personalizadas */
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #ecf0f1;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff;
        border-bottom: 2px solid #3498db;
    }
</style>
""", unsafe_allow_html=True)

# --- CARGA SEGURA DE LIBRERÍAS ---
try:
    from fpdf import FPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# --- MOTOR PDF (CACHÉ) ---
if PDF_AVAILABLE:
    class PDF(FPDF):
        def header(self):
            self.set_font('Helvetica', 'B', 14)
            self.cell(0, 10, 'EV Market Intelligence Report', 0, 1, 'C')
            self.ln(5)
        def footer(self):
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 8)
            self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    def clean_text(text):
        try: return str(text).encode('latin-1', 'replace').decode('latin-1')
        except: return str(text)

    @st.cache_data(show_spinner=False)
    def generar_pdf(df_dict, titulo, modo):
        df = pd.DataFrame(df_dict)
        pdf = PDF()
        pdf.add_page()
        
        # Título
        pdf.set_font("Helvetica", 'B', 16)
        pdf.cell(0, 10, clean_text(titulo), 0, 1, 'L')
        pdf.set_font("Helvetica", 'I', 10)
        pdf.cell(0, 10, f"Modo de Analisis: {clean_text(modo)}", 0, 1, 'L')
        pdf.ln(5)
        
        # Resumen Ejecutivo
        total_vol = df['CANTIDAD'].sum()
        total_val = df['VALOR US$ CIF'].sum()
        cif_avg = total_val/total_vol if total_vol else 0
        
        pdf.set_fill_color(240, 240, 240)
        pdf.rect(10, 40, 190, 25, 'F')
        pdf.set_y(45)
        pdf.set_font("Helvetica", 'B', 12)
        pdf.cell(60, 10, f"Volumen Total: {total_vol:,.0f}", 0, 0, 'C')
        pdf.cell(60, 10, f"Inversion: ${total_val/1e6:,.1f} M", 0, 0, 'C')
        pdf.cell(60, 10, f"CIF Promedio: ${cif_avg:,.0f}", 0, 1, 'C')
        pdf.ln(15)

        # Tablas Dinámicas según Modo
        pdf.set_font("Helvetica", 'B', 12)
        
        if modo == "Deep Dive":
            pdf.cell(0, 10, "Top 10 Modelos (Pareto)", 0, 1)
            pdf.set_font("Helvetica", '', 10)
            top_mod = df.groupby('MODELO')['CANTIDAD'].sum().sort_values(ascending=False).head(10)
            for m, v in top_mod.items():
                pdf.cell(140, 8, clean_text(m)[:50], 1)
                pdf.cell(40, 8, f"{v:,.0f}", 1, 1, 'R')
                
        else: # Comparativo o Total
            pdf.cell(0, 10, "Ranking de Marcas", 0, 1)
            pdf.set_font("Helvetica", '', 10)
            top_mk = df.groupby('MARCA')['CANTIDAD'].sum().sort_values(ascending=False).head(10)
            for m, v in top_mk.items():
                pdf.cell(140, 8, clean_text(m), 1)
                pdf.cell(40, 8, f"{v:,.0f}", 1, 1, 'R')

        return pdf.output(dest='S').encode('latin-1')

# --- CARGA DE DATOS ---
@st.cache_data
def cargar_datos():
    archivo = "historial_lite.parquet"
    if not os.path.exists(archivo): return None
    try:
        df = pd.read_parquet(archivo)
        df.columns = df.columns.str.strip().str.upper()
        
        # Normalización Rápida
        if 'MARCA' in df.columns:
            df['MARCA'] = df['MARCA'].astype(str).str.upper().replace({'M.G.': 'MG', 'MORRIS GARAGES': 'MG', 'BYD AUTO': 'BYD'})
        
        cols_str = ['MODELO', 'EMPRESA', 'COMBUSTIBLE', 'CARROCERIA', 'MES']
        for c in cols_str:
            if c in df.columns: df[c] = df[c].astype(str).str.strip().str.upper()
            
        for c in ['CANTIDAD', 'VALOR US$ CIF', 'FLETE']:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
        if 'FECHA' in df.columns:
            df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
            df['AÑO'] = df['FECHA'].dt.year
            df['MES_NUM'] = df['FECHA'].dt.month

        # Cálculos Unitarios
        if 'VALOR US$ CIF' in df.columns:
            df['CIF_UNITARIO'] = (df['VALOR US$ CIF'] / df['CANTIDAD']).replace([np.inf, -np.inf], 0).fillna(0)
        if 'FLETE' in df.columns:
            df['FLETE_UNITARIO'] = (df['FLETE'] / df['CANTIDAD']).replace([np.inf, -np.inf], 0).fillna(0)
            
        return df
    except: return None

# --- SIDEBAR ---
with st.sidebar:
    st.title("🧠 Market Intelligence")
    df = cargar_datos()
    
    if df is not None:
        st.success(f"Base de Datos Activa: {len(df):,.0f} Reg.")
        st.markdown("---")
        # MENÚ PRINCIPAL DIVIDIDO EN 3
        menu = st.radio("Selecciona Módulo:", 
                        ["🌍 Mercado Total", "⚔️ Benchmarking (Comparativo)", "🔍 Análisis de Marca (Deep Dive)"])
        st.markdown("---")
    else:
        st.error("⚠️ Error: No se detectan datos.")

# --- LÓGICA DE MÓDULOS ---
if df is not None:
    
    # ==============================================================================
    # 1. 🌍 MERCADO TOTAL (MACRO)
    # ==============================================================================
    if menu == "🌍 Mercado Total":
        st.title("🌍 Visión Macro del Mercado")
        
        # Filtros Ligeros
        yrs = st.multiselect("Periodo de Análisis", sorted(df['AÑO'].dropna().unique().astype(int), reverse=True), default=sorted(df['AÑO'].dropna().unique().astype(int), reverse=True)[:2])
        df_m = df[df['AÑO'].isin(yrs)].copy()
        
        # KPIs Macro
        c1, c2, c3, c4 = st.columns(4)
        total_u = df_m['CANTIDAD'].sum()
        total_val = df_m['VALOR US$ CIF'].sum()
        c1.metric("Volumen Total", f"{total_u:,.0f}")
        c2.metric("Valor CIF Total", f"${total_val/1e6:,.1f} M")
        c3.metric("Precio Promedio", f"${(total_val/total_u):,.0f}")
        c4.metric("Marcas Activas", f"{df_m['MARCA'].nunique()}")
        
        st.divider()
        
        # GRÁFICOS INTELIGENTES
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📈 Evolución Temporal")
            # Agrupación por Mes y Año
            mensual = df_m.groupby(['AÑO', 'MES_NUM'])['CANTIDAD'].sum().reset_index()
            # Crear columna fecha artificial para ordenar bien
            mensual['Fecha'] = pd.to_datetime(mensual['AÑO'].astype(str) + '-' + mensual['MES_NUM'].astype(str) + '-01')
            
            fig = px.line(mensual, x='Fecha', y='CANTIDAD', markers=True, title="Tendencia de Importaciones")
            st.plotly_chart(fig, use_container_width=True)
            
        with col2:
            st.subheader("⛽ Mix de Energía")
            mix = df_m.groupby('COMBUSTIBLE')['CANTIDAD'].sum().reset_index()
            fig2 = px.pie(mix, values='CANTIDAD', names='COMBUSTIBLE', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig2, use_container_width=True)

        # TABLA DE LIDERAZGO
        st.subheader("🏆 Ranking de Jugadores (Market Share)")
        share = df_m.groupby('MARCA')['CANTIDAD'].sum().sort_values(ascending=False).reset_index()
        share['Share %'] = (share['CANTIDAD'] / total_u) * 100
        share['Acumulado %'] = share['Share %'].cumsum()
        
        st.dataframe(share.head(20).style.format({'Share %': '{:.1f}%', 'Acumulado %': '{:.1f}%'}), use_container_width=True)

    # ==============================================================================
    # 2. ⚔️ BENCHMARKING (COMPARATIVO)
    # ==============================================================================
    elif menu == "⚔️ Benchmarking (Comparativo)":
        with st.sidebar:
            st.subheader("Configuración de Guerra")
            yrs = st.multiselect("Años", sorted(df['AÑO'].unique(), reverse=True), default=sorted(df['AÑO'].unique(), reverse=True)[:1])
            
            df_curr = df[df['AÑO'].isin(yrs)]
            top_brands = df_curr['MARCA'].value_counts().head(3).index.tolist()
            mks = st.multiselect("Competidores", sorted(df_curr['MARCA'].unique()), default=top_brands)
        
        df_c = df_curr[df_curr['MARCA'].isin(mks)].copy()
        
        st.title("⚔️ Análisis Comparativo de Competencia")
        
        if not df_c.empty:
            t1, t2, t3 = st.tabs(["📊 Volumen & Share", "💰 Estrategia de Precios", "🕵️ Mercado Gris"])
            
            with t1:
                col_b1, col_b2 = st.columns([2,1])
                with col_b1:
                    st.subheader("Batalla de Volumen")
                    fig = px.bar(df_c.groupby(['MARCA', 'AÑO'])['CANTIDAD'].sum().reset_index(), 
                                 x='MARCA', y='CANTIDAD', color='AÑO', barmode='group', text_auto=True)
                    st.plotly_chart(fig, use_container_width=True)
                with col_b2:
                    st.subheader("Peso por Carrocería")
                    # Stacked bar 100% para ver mix de producto
                    seg = df_c.groupby(['MARCA', 'CARROCERIA'])['CANTIDAD'].sum().reset_index()
                    fig_s = px.bar(seg, x='MARCA', y='CANTIDAD', color='CARROCERIA', title="Mix de Producto")
                    st.plotly_chart(fig_s, use_container_width=True)
            
            with t2:
                st.subheader("Posicionamiento de Precios (Box Plot)")
                st.info("💡 **Inteligencia:** Este gráfico revela la estrategia. Cajas alargadas = Portafolio amplio (Baratos y Caros). Cajas compactas = Precios estandarizados.")
                # Filtramos basura para limpiar el gráfico
                df_p = df_c[(df_c['CIF_UNITARIO'] > 2000) & (df_c['CIF_UNITARIO'] < 150000)]
                fig_box = px.box(df_p, x='MARCA', y='CIF_UNITARIO', color='MARCA', points='outliers')
                st.plotly_chart(fig_box, use_container_width=True)

            with t3:
                st.subheader("Análisis de Fuga (Oficial vs Paralelo)")
                # Cálculo Vectorizado Inteligente
                oficiales = df_c.groupby(['MARCA', 'EMPRESA'])['CANTIDAD'].sum().reset_index().sort_values(['MARCA','CANTIDAD'], ascending=[True, False]).drop_duplicates('MARCA')
                oficiales = oficiales.rename(columns={'EMPRESA':'OFICIAL_NAME'})[['MARCA','OFICIAL_NAME']]
                
                df_c = df_c.merge(oficiales, on='MARCA', how='left')
                df_c['CANAL'] = np.where(df_c['EMPRESA'] == df_c['OFICIAL_NAME'], 'OFICIAL', 'GRIS')
                
                # Gráfico
                resumen_gris = df_c.groupby(['MARCA', 'CANAL'])['CANTIDAD'].sum().unstack().fillna(0)
                resumen_gris['Total'] = resumen_gris['OFICIAL'] + resumen_gris['GRIS']
                resumen_gris['% Fuga'] = (resumen_gris['GRIS'] / resumen_gris['Total']) * 100
                resumen_gris = resumen_gris.sort_values('% Fuga', ascending=False).reset_index()
                
                fig_g = px.bar(resumen_gris, x='MARCA', y=['OFICIAL', 'GRIS'], title="Volumen por Canal", color_discrete_map={'OFICIAL':'#27ae60', 'GRIS':'#7f8c8d'})
                fig_g.add_trace(go.Scatter(x=resumen_gris['MARCA'], y=resumen_gris['% Fuga'], name='% Fuga', yaxis='y2', line=dict(color='red', width=3)))
                fig_g.update_layout(yaxis2=dict(overlaying='y', side='right', range=[0, 100], title="% Fuga"))
                st.plotly_chart(fig_g, use_container_width=True)

    # ==============================================================================
    # 3. 🔍 ANÁLISIS DE MARCA (DEEP DIVE)
    # ==============================================================================
    elif menu == "🔍 Análisis de Marca (Deep Dive)":
        with st.sidebar:
            st.subheader("Filtros de Auditoría")
            y_dd = st.selectbox("Año Fiscal", sorted(df['AÑO'].unique(), reverse=True))
            df_y = df[df['AÑO'] == y_dd]
            
            brand_dd = st.selectbox("Marca Objetivo", sorted(df_y['MARCA'].unique()))
            df_b = df_y[df_y['MARCA'] == brand_dd].copy()
        
        st.title(f"🔍 Auditoría Profunda: {brand_dd} ({y_dd})")
        
        if not df_b.empty:
            # KPIS DE MARCA
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Unidades", f"{df_b['CANTIDAD'].sum():,.0f}")
            k2.metric("Ticket Promedio", f"${df_b['CIF_UNITARIO'].mean():,.0f}")
            k3.metric("Flete Promedio", f"${df_b['FLETE_UNITARIO'].mean():,.0f}")
            k4.metric("Modelos Activos", f"{df_b['MODELO'].nunique()}")
            
            tab_a, tab_b, tab_c = st.tabs(["📊 Modelos & Pareto", "🔮 Proyección & Tendencia", "🚢 Logística & Importadores"])
            
            with tab_a:
                c_pa1, c_pa2 = st.columns([2,1])
                with c_pa1:
                    st.subheader("Análisis de Pareto (80/20)")
                    pareto = df_b.groupby('MODELO')['CANTIDAD'].sum().sort_values(ascending=False).reset_index()
                    pareto['Acum'] = pareto['CANTIDAD'].cumsum()
                    pareto['%'] = (pareto['Acum'] / pareto['CANTIDAD'].sum()) * 100
                    pareto['Color'] = np.where(pareto['%'] <= 80, '#27ae60', '#bdc3c7')
                    
                    fig_p = go.Figure()
                    fig_p.add_trace(go.Bar(x=pareto['MODELO'], y=pareto['CANTIDAD'], marker_color=pareto['Color'], name='Volumen'))
                    fig_p.add_trace(go.Scatter(x=pareto['MODELO'], y=pareto['%'], yaxis='y2', name='% Acumulado', line=dict(color='red')))
                    fig_p.update_layout(yaxis2=dict(overlaying='y', side='right', range=[0, 110]))
                    st.plotly_chart(fig_p, use_container_width=True)
                
                with c_pa2:
                    st.subheader("Lista de Precios")
                    precios = df_b.groupby('MODELO').agg(Vol=('CANTIDAD','sum'), Precio=('CIF_UNITARIO','mean')).sort_values('Vol', ascending=False)
                    st.dataframe(precios.style.format({'Precio': '${:,.0f}'}), use_container_width=True)

            with tab_b:
                st.subheader("Proyección Matemática (Tendencia Lineal)")
                mensual = df_b.groupby('MES_NUM')['CANTIDAD'].sum().reset_index()
                if len(mensual) > 1:
                    try:
                        fig_tr = px.scatter(mensual, x='MES_NUM', y='CANTIDAD', trendline="ols", trendline_color_override="red", title="Forecast de Ventas")
                        fig_tr.update_traces(mode='lines+markers')
                        st.plotly_chart(fig_tr, use_container_width=True)
                        st.caption("La línea roja indica la dirección matemática basada en el histórico reciente.")
                    except:
                        st.line_chart(mensual.set_index('MES_NUM'))
                else: st.warning("Datos insuficientes para proyección.")

            with tab_c:
                col_imp1, col_imp2 = st.columns(2)
                with col_imp1:
                    st.subheader("Rango de Negociación (Fletes)")
                    # Filtro de outliers de flete
                    fletes = df_b[(df_b['FLETE_UNITARIO'] > 100) & (df_b['FLETE_UNITARIO'] < 8000)]
                    if not fletes.empty:
                        fig_f = px.box(fletes, x='MES_NUM', y='FLETE_UNITARIO', title="Variabilidad de Costo Logístico")
                        st.plotly_chart(fig_f, use_container_width=True)
                    else: st.info("Sin datos de fletes válidos.")
                
                with col_imp2:
                    st.subheader("Top Importadores")
                    imps = df_b.groupby('EMPRESA')['CANTIDAD'].sum().sort_values(ascending=False).head(10)
                    st.dataframe(imps, use_container_width=True)

    # ==============================================================================
    # BOTÓN DE PDF (GENÉRICO Y SEGURO)
    # ==============================================================================
    if PDF_AVAILABLE:
        st.sidebar.divider()
        st.sidebar.markdown("### 📥 Reportes")
        
        # Preparamos los datos actuales para el reporte
        if menu == "🌍 Mercado Total":
            data_pdf = df_m if 'df_m' in locals() else df.head(100)
        elif menu == "⚔️ Benchmarking (Comparativo)":
            data_pdf = df_c if 'df_c' in locals() else df.head(100)
        else:
            data_pdf = df_b if 'df_b' in locals() else df.head(100)
            
        if st.sidebar.button("📄 Generar PDF Ejecutivo"):
            try:
                pdf_bytes = generar_pdf(data_pdf.to_dict(orient='list'), f"Reporte: {menu}", menu)
                st.sidebar.download_button("💾 Descargar PDF", pdf_bytes, "Reporte_Intel_Mercado.pdf", "application/pdf")
            except Exception as e:
                st.sidebar.error("Error al generar PDF. Intenta filtrar menos datos.")

    # Limpieza de Memoria
    gc.collect()

else:
    st.info("Esperando conexión con GitHub...")

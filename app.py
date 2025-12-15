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
    page_icon="🚀",
    initial_sidebar_state="expanded"
)

# --- ESTILOS VISUALES ---
st.markdown("""
<style>
    .main {background-color: #f8f9fa;}
    h1, h2, h3 {font-family: 'Helvetica', sans-serif; color: #2c3e50;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    /* Ajuste para móviles */
    @media (max-width: 768px) { .block-container {padding: 0.5rem;} }
</style>
""", unsafe_allow_html=True)

# --- MOTOR DE PDF EJECUTIVO (OPTIMIZADO) ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Reporte de Inteligencia de Mercado', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

def clean_text(text):
    """Limpia caracteres para que FPDF no falle con tildes o símbolos"""
    try: return str(text).encode('latin-1', 'replace').decode('latin-1')
    except: return str(text)

@st.cache_data(show_spinner=False)
def generar_pdf_ejecutivo(df_dict, titulo, subtitulo):
    # Reconstruimos DF ligero
    df = pd.DataFrame(df_dict)
    
    pdf = PDF()
    pdf.add_page()
    
    # 1. ENCABEZADO
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, clean_text(titulo), 0, 1, 'L')
    pdf.set_font("Arial", 'I', 11)
    pdf.cell(0, 10, clean_text(subtitulo), 0, 1, 'L')
    pdf.ln(5)
    
    # 2. KPIS PRINCIPALES (Resumen)
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

    # 3. TABLA DE LIDERAZGO (TOP 15)
    # En lugar de imprimir todo, imprimimos solo el TOP 15 para ahorrar memoria
    pdf.set_font("Arial", 'B', 12)
    agrupador = 'MODELO' if 'MODELO' in df.columns else 'MARCA'
    pdf.cell(0, 10, f"Ranking Top 15 por {clean_text(agrupador)}", 0, 1)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(200, 200, 200)
    pdf.cell(140, 8, clean_text(agrupador), 1, 0, 'C', 1)
    pdf.cell(50, 8, "Unidades", 1, 1, 'C', 1)
    
    pdf.set_font("Arial", '', 10)
    top_data = df.groupby(agrupador)['CANTIDAD'].sum().sort_values(ascending=False).head(15)
    
    for nombre, val in top_data.items():
        pdf.cell(140, 8, clean_text(str(nombre))[:60], 1) # Cortamos nombres muy largos
        pdf.cell(50, 8, f"{val:,.0f}", 1, 1, 'R')
    
    pdf.ln(10)

    # 4. MERCADO GRIS (Si aplica)
    if 'EMPRESA' in df.columns and 'MARCA' in df.columns:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Analisis de Importadores (Top 5)", 0, 1)
        pdf.set_font("Arial", '', 10)
        
        top_imp = df.groupby('EMPRESA')['CANTIDAD'].sum().sort_values(ascending=False).head(5)
        for emp, val in top_imp.items():
            pdf.cell(140, 8, clean_text(str(emp))[:60], 1)
            pdf.cell(50, 8, f"{val:,.0f}", 1, 1, 'R')

    return pdf.output(dest='S').encode('latin-1')

# --- CARGA DE DATOS ---
@st.cache_data
def cargar_datos():
    archivo = "historial_lite.parquet"
    if not os.path.exists(archivo): return None
    try:
        df = pd.read_parquet(archivo)
        df.columns = df.columns.str.strip().str.upper()
        
        # Limpiezas
        for c in ['MARCA', 'MODELO', 'EMPRESA', 'COMBUSTIBLE', 'CARROCERIA']:
            if c in df.columns: df[c] = df[c].astype(str).str.strip().str.upper()
        if 'MARCA' in df.columns: df['MARCA'] = df['MARCA'].replace({'M.G.': 'MG', 'MORRIS GARAGES': 'MG', 'BYD AUTO': 'BYD'})
        
        for c in ['CANTIDAD', 'VALOR US$ CIF', 'FLETE']:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
        # FIX FECHAS ROBUSTO
        if 'FECHA' in df.columns:
            df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
            df = df.dropna(subset=['FECHA']) # Eliminar fechas invalidas
            df['AÑO'] = df['FECHA'].dt.year.astype(int)
            df['MES_NUM'] = df['FECHA'].dt.month.astype(int)

        # Unitarios
        if 'VALOR US$ CIF' in df.columns:
            df['CIF_UNITARIO'] = (df['VALOR US$ CIF'] / df['CANTIDAD']).replace([np.inf, -np.inf], 0).fillna(0)
        if 'FLETE' in df.columns:
            df['FLETE_UNITARIO'] = (df['FLETE'] / df['CANTIDAD']).replace([np.inf, -np.inf], 0).fillna(0)
            
        return df
    except: return None

# --- APP PRINCIPAL ---
with st.sidebar:
    st.title("🧠 Market Intel")
    df = cargar_datos()
    
    if df is not None:
        st.success(f"Online: {len(df):,.0f} Regs")
        st.divider()
        menu = st.radio("Módulo:", ["🌍 Mercado Total", "⚔️ Benchmarking", "🔍 Deep Dive"])
        st.divider()
    else:
        st.error("Error cargando datos.")

if df is not None:
    
    # ----------------------------------------------------
    # 1. 🌍 MERCADO TOTAL
    # ----------------------------------------------------
    if menu == "🌍 Mercado Total":
        st.title("🌍 Visión Macro")
        yrs = st.multiselect("Periodo", sorted(df['AÑO'].unique(), reverse=True), default=sorted(df['AÑO'].unique(), reverse=True)[:2])
        df_m = df[df['AÑO'].isin(yrs)].copy()
        
        # KPIs
        with st.container(border=True):
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Volumen", f"{df_m['CANTIDAD'].sum():,.0f}")
            k2.metric("Valor CIF", f"${df_m['VALOR US$ CIF'].sum()/1e6:,.1f} M")
            k3.metric("Ticket Prom.", f"${df_m['CIF_UNITARIO'].mean():,.0f}")
            k4.metric("Marcas", f"{df_m['MARCA'].nunique()}")
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("Tendencia")
            # Agrupación segura para gráfica
            mensual = df_m.groupby(['AÑO', 'MES_NUM'])['CANTIDAD'].sum().reset_index()
            mensual['Fecha'] = pd.to_datetime(mensual['AÑO'].astype(str) + '-' + mensual['MES_NUM'].astype(str) + '-01')
            st.plotly_chart(px.line(mensual, x='Fecha', y='CANTIDAD', markers=True), use_container_width=True)
        with c2:
            st.subheader("Energía")
            st.plotly_chart(px.pie(df_m, values='CANTIDAD', names='COMBUSTIBLE', hole=0.4), use_container_width=True)
            
        st.subheader("Ranking de Jugadores")
        top_share = df_m.groupby('MARCA')['CANTIDAD'].sum().sort_values(ascending=False).reset_index().head(20)
        top_share['Share %'] = (top_share['CANTIDAD'] / top_share['CANTIDAD'].sum()) * 100
        st.dataframe(top_share.style.format({'Share %': '{:.1f}%'}), use_container_width=True)

        # PREPARAR DATA PDF
        pdf_data = df_m
        titulo_pdf = "Reporte Macro Mercado"

    # ----------------------------------------------------
    # 2. ⚔️ BENCHMARKING
    # ----------------------------------------------------
    elif menu == "⚔️ Benchmarking":
        st.title("⚔️ Comparativo")
        with st.sidebar:
            yrs_b = st.multiselect("Años", sorted(df['AÑO'].unique(), reverse=True), default=sorted(df['AÑO'].unique(), reverse=True)[:1])
            df_curr = df[df['AÑO'].isin(yrs_b)]
            
            mks_avail = sorted(df_curr['MARCA'].unique())
            if st.checkbox("Seleccionar Todas", value=False): mks = mks_avail
            else: mks = st.multiselect("Marcas", mks_avail, default=df_curr['MARCA'].value_counts().head(3).index.tolist())

        df_c = df_curr[df_curr['MARCA'].isin(mks)].copy()
        
        if not df_c.empty:
            t1, t2 = st.tabs(["Volumen & Precios", "Mercado Gris"])
            
            with t1:
                c_b1, c_b2 = st.columns(2)
                with c_b1:
                    st.plotly_chart(px.bar(df_c, x='MARCA', y='CANTIDAD', color='AÑO', title="Volumen"), use_container_width=True)
                with c_b2:
                    df_p = df_c[(df_c['CIF_UNITARIO'] > 2000) & (df_c['CIF_UNITARIO'] < 150000)]
                    st.plotly_chart(px.box(df_p, x='MARCA', y='CIF_UNITARIO', title="Precios"), use_container_width=True)
            
            with t2:
                # Lógica Rápida Gris
                oficiales = df_c.groupby(['MARCA', 'EMPRESA'])['CANTIDAD'].sum().reset_index().sort_values(['MARCA','CANTIDAD'], ascending=[False, False]).drop_duplicates('MARCA')
                oficiales = oficiales.rename(columns={'EMPRESA':'OFICIAL'})[['MARCA','OFICIAL']]
                df_c = df_c.merge(oficiales, on='MARCA', how='left')
                df_c['TIPO'] = np.where(df_c['EMPRESA'] == df_c['OFICIAL'], 'OFICIAL', 'GRIS')
                
                resumen = df_c.groupby(['MARCA', 'TIPO'])['CANTIDAD'].sum().unstack().fillna(0).reset_index()
                st.plotly_chart(px.bar(resumen, x='MARCA', y=['OFICIAL', 'GRIS'] if 'GRIS' in resumen else ['OFICIAL'], 
                                       title="Oficial vs Gris", color_discrete_map={'OFICIAL':'#2ecc71', 'GRIS':'#95a5a6'}), use_container_width=True)
        
        # PREPARAR DATA PDF
        pdf_data = df_c
        titulo_pdf = "Reporte Competitivo"

    # ----------------------------------------------------
    # 3. 🔍 DEEP DIVE
    # ----------------------------------------------------
    elif menu == "🔍 Deep Dive":
        with st.sidebar:
            y_dd = st.selectbox("Año", sorted(df['AÑO'].unique(), reverse=True))
            df_y = df[df['AÑO'] == y_dd]
            brand_dd = st.selectbox("Marca", sorted(df_y['MARCA'].unique()))
            df_b = df_y[df_y['MARCA'] == brand_dd].copy()
        
        st.title(f"🔍 Auditoría: {brand_dd}")
        
        if not df_b.empty:
            with st.container(border=True):
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Volumen", f"{df_b['CANTIDAD'].sum():,.0f}")
                k2.metric("CIF Prom.", f"${df_b['CIF_UNITARIO'].mean():,.0f}")
                k3.metric("Flete Prom.", f"${df_b['FLETE_UNITARIO'].mean():,.0f}")
                k4.metric("Modelos", f"{df_b['MODELO'].nunique()}")
            
            tab_a, tab_b = st.tabs(["Pareto Modelos", "Logística & Importadores"])
            
            with tab_a:
                pareto = df_b.groupby('MODELO')['CANTIDAD'].sum().sort_values(ascending=False).reset_index()
                pareto['%'] = (pareto['CANTIDAD'].cumsum() / pareto['CANTIDAD'].sum()) * 100
                
                fig_p = go.Figure()
                fig_p.add_trace(go.Bar(x=pareto['MODELO'], y=pareto['CANTIDAD'], name='Volumen'))
                fig_p.add_trace(go.Scatter(x=pareto['MODELO'], y=pareto['%'], yaxis='y2', name='%', line=dict(color='red')))
                fig_p.update_layout(yaxis2=dict(overlaying='y', side='right', range=[0, 110]))
                st.plotly_chart(fig_p, use_container_width=True)
                
            with tab_b:
                c1, c2 = st.columns(2)
                with c1:
                    fletes = df_b[(df_b['FLETE_UNITARIO'] > 100) & (df_b['FLETE_UNITARIO'] < 8000)]
                    if not fletes.empty: st.plotly_chart(px.box(fletes, x='MES_NUM', y='FLETE_UNITARIO', title="Fletes"), use_container_width=True)
                with c2:
                    st.subheader("Top Importadores")
                    st.dataframe(df_b.groupby('EMPRESA')['CANTIDAD'].sum().sort_values(ascending=False).head(10), use_container_width=True)
        
        # PREPARAR DATA PDF
        pdf_data = df_b
        titulo_pdf = f"Reporte Detallado: {brand_dd} ({y_dd})"

    # ==============================================================================
    # 4. BOTÓN DESCARGA PDF (EN SIDEBAR)
    # ==============================================================================
    if 'pdf_data' in locals() and not pdf_data.empty:
        st.sidebar.divider()
        st.sidebar.markdown("### 📥 Exportar")
        
        if st.sidebar.button("📄 Generar PDF Ejecutivo"):
            try:
                # Convertimos a Dict para el caché (Súper Rápido)
                data_dict = pdf_data.to_dict(orient='list')
                pdf_bytes = generar_pdf_ejecutivo(data_dict, titulo_pdf, f"Generado el {pd.Timestamp.now().date()}")
                
                st.sidebar.download_button(
                    label="💾 Descargar Archivo",
                    data=pdf_bytes,
                    file_name="Reporte_Inteligencia.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.sidebar.error(f"Error generando PDF: {e}")

    # Limpiar RAM
    gc.collect()

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
    page_title="Market Intelligence CR", 
    layout="wide", 
    page_icon="🇨🇷",
    initial_sidebar_state="expanded"
)

# --- ESTILOS PROFESIONALES ---
st.markdown("""
<style>
    .main {background-color: #f8f9fa;}
    h1, h2, h3 {font-family: 'Helvetica', sans-serif; color: #2c3e50;}
    .block-container {padding-top: 1.5rem; padding-bottom: 3rem;}
    
    /* KPI Cards */
    div[data-testid="stMetric"] {
        background-color: white;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border-top: 3px solid #3498db;
    }
</style>
""", unsafe_allow_html=True)

# --- MOTOR DE REPORTE PDF (EJECUTIVO) ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Reporte de Inteligencia de Mercado Automotriz (CR)', 0, 1, 'C')
        self.ln(5)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pag {self.page_no()} - Generado con Market Intelligence', 0, 0, 'C')

def clean_text(text):
    try: return str(text).encode('latin-1', 'replace').decode('latin-1')
    except: return str(text)

@st.cache_data(show_spinner=False)
def generar_pdf_ejecutivo(df_dict, titulo, subtitulo):
    df = pd.DataFrame(df_dict)
    pdf = PDF()
    pdf.add_page()
    
    # 1. TÍTULO
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, clean_text(titulo), 0, 1, 'L')
    pdf.set_font("Arial", 'I', 11)
    pdf.cell(0, 10, clean_text(subtitulo), 0, 1, 'L')
    pdf.ln(5)
    
    # 2. KPIS RESUMEN
    total_vol = df['CANTIDAD'].sum()
    total_val = df['VALOR US$ CIF'].sum()
    cif_prom = total_val/total_vol if total_vol else 0
    
    pdf.set_fill_color(240, 240, 240)
    pdf.rect(10, 45, 190, 20, 'F')
    pdf.set_y(50)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(63, 10, f"Volumen: {total_vol:,.0f}", 0, 0, 'C')
    pdf.cell(63, 10, f"Inversion: ${total_val/1e6:,.1f} M", 0, 0, 'C')
    pdf.cell(63, 10, f"CIF Prom: ${cif_prom:,.0f}", 0, 1, 'C')
    pdf.ln(15)

    # 3. TABLA TOP 15
    pdf.set_font("Arial", 'B', 12)
    agrupador = 'MODELO' if 'MODELO' in df.columns else 'MARCA'
    pdf.cell(0, 10, f"Top 15 {clean_text(agrupador)} por Volumen", 0, 1)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(140, 8, clean_text(agrupador), 1, 0, 'L', 1)
    pdf.cell(50, 8, "Unidades", 1, 1, 'R', 1)
    
    pdf.set_font("Arial", '', 10)
    top = df.groupby(agrupador)['CANTIDAD'].sum().sort_values(ascending=False).head(15)
    
    for k, v in top.items():
        pdf.cell(140, 8, clean_text(str(k))[:60], 1)
        pdf.cell(50, 8, f"{v:,.0f}", 1, 1, 'R')
    
    # 4. MERCADO GRIS (SI APLICA)
    if 'EMPRESA' in df.columns:
        pdf.ln(10)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Top Importadores (Oficial vs Gris)", 0, 1)
        pdf.set_font("Arial", '', 10)
        imps = df.groupby('EMPRESA')['CANTIDAD'].sum().sort_values(ascending=False).head(5)
        for k, v in imps.items():
            pdf.cell(140, 8, clean_text(str(k))[:60], 1)
            pdf.cell(50, 8, f"{v:,.0f}", 1, 1, 'R')

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
            df = df.dropna(subset=['FECHA'])
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
        st.success(f"Conectado: {len(df):,.0f} Regs")
        st.divider()
        menu = st.radio("Estrategia:", ["🌍 Visión País", "⚔️ Guerra de Marcas", "🔍 Auditoría Marca"])
        st.divider()
    else:
        st.error("Error: No data")

if df is not None:
    
    # ----------------------------------------------------
    # 1. VISIÓN PAÍS (MACRO)
    # ----------------------------------------------------
    if menu == "🌍 Visión País":
        st.title("🌍 Inteligencia de Mercado: Costa Rica")
        
        yrs = st.multiselect("Periodo", sorted(df['AÑO'].unique(), reverse=True), default=sorted(df['AÑO'].unique(), reverse=True)[:2])
        df_m = df[df['AÑO'].isin(yrs)].copy()
        
        # KPIs con Crecimiento
        vol_total = df_m['CANTIDAD'].sum()
        val_total = df_m['VALOR US$ CIF'].sum()
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Volumen Total", f"{vol_total:,.0f}")
        k2.metric("Inversión CIF", f"${val_total/1e6:,.1f} M")
        k3.metric("Ticket Promedio", f"${(val_total/vol_total):,.0f}")
        k4.metric("Marcas Activas", f"{df_m['MARCA'].nunique()}")
        
        st.markdown("---")
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("Tendencia Mensual")
            mensual = df_m.groupby(['AÑO', 'MES_NUM'])['CANTIDAD'].sum().reset_index()
            mensual['Fecha'] = pd.to_datetime(mensual['AÑO'].astype(str) + '-' + mensual['MES_NUM'].astype(str) + '-01')
            st.plotly_chart(px.line(mensual, x='Fecha', y='CANTIDAD', markers=True), use_container_width=True)
        
        with c2:
            st.subheader("Segmentación de Precios")
            # Nueva Lógica de Auditoría: Segmentación
            bins = [0, 15000, 25000, 40000, 70000, 1000000]
            labels = ['Económico (<15k)', 'Entrada (15-25k)', 'Medio (25-40k)', 'Premium (40-70k)', 'Lujo (>70k)']
            df_m['SEGMENTO'] = pd.cut(df_m['CIF_UNITARIO'], bins=bins, labels=labels)
            seg = df_m.groupby('SEGMENTO', observed=True)['CANTIDAD'].sum().reset_index()
            st.plotly_chart(px.pie(seg, values='CANTIDAD', names='SEGMENTO', hole=0.4), use_container_width=True)

        # PREPARAR PDF
        pdf_data = df_m
        titulo_pdf = "Reporte Macro Pais"

    # ----------------------------------------------------
    # 2. GUERRA DE MARCAS (BENCHMARK)
    # ----------------------------------------------------
    elif menu == "⚔️ Guerra de Marcas":
        st.title("⚔️ Benchmarking Competitivo")
        
        with st.sidebar:
            yrs_b = st.multiselect("Años", sorted(df['AÑO'].unique(), reverse=True), default=sorted(df['AÑO'].unique(), reverse=True)[:1])
            df_curr = df[df['AÑO'].isin(yrs_b)]
            
            mks_avail = sorted(df_curr['MARCA'].unique())
            if st.checkbox("Seleccionar Todas", value=False): mks = mks_avail
            else: mks = st.multiselect("Competidores", mks_avail, default=df_curr['MARCA'].value_counts().head(3).index.tolist())

        df_c = df_curr[df_curr['MARCA'].isin(mks)].copy()
        
        if not df_c.empty:
            t1, t2 = st.tabs(["📊 Market Share", "🕵️ Mercado Gris (Auditoría)"])
            
            with t1:
                col_vol, col_pr = st.columns(2)
                with col_vol:
                    st.subheader("Volumen por Marca")
                    st.plotly_chart(px.bar(df_c, x='MARCA', y='CANTIDAD', color='AÑO', text_auto=True), use_container_width=True)
                with col_pr:
                    st.subheader("Estrategia de Precios")
                    # Filtramos errores de digitación (precios < 1000 o > 200k)
                    df_clean_price = df_c[(df_c['CIF_UNITARIO'] > 1000) & (df_c['CIF_UNITARIO'] < 200000)]
                    st.plotly_chart(px.box(df_clean_price, x='MARCA', y='CIF_UNITARIO', points="outliers"), use_container_width=True)
            
            with t2:
                # ALGORITMO DE AUDITORÍA DE MERCADO GRIS
                gb = df_c.groupby(['MARCA', 'EMPRESA'])['CANTIDAD'].sum().reset_index()
                # Encontramos al "Líder" de cada marca
                lideres = gb.sort_values(['MARCA', 'CANTIDAD'], ascending=[True, False]).drop_duplicates('MARCA')
                lideres = lideres.rename(columns={'EMPRESA': 'LIDER_DETECTADO'})[['MARCA', 'LIDER_DETECTADO']]
                
                df_c = df_c.merge(lideres, on='MARCA', how='left')
                df_c['CANAL'] = np.where(df_c['EMPRESA'] == df_c['LIDER_DETECTADO'], 'OFICIAL (Probable)', 'GRIS')
                
                # Gráfico
                resumen = df_c.groupby(['MARCA', 'CANAL'])['CANTIDAD'].sum().unstack().fillna(0).reset_index()
                st.plotly_chart(px.bar(resumen, x='MARCA', y=[c for c in resumen.columns if c!='MARCA'], 
                                       title="Volumen: Oficial vs Paralelo", barmode='group'), use_container_width=True)
                
                # Tabla de Auditoría
                st.info("ℹ️ El sistema asume que la empresa con mayor volumen es el Distribuidor Oficial.")
                st.write(" **Detalle de 'Líderes Detectados':**")
                st.dataframe(lideres.set_index('MARCA'), use_container_width=True)

        pdf_data = df_c
        titulo_pdf = "Reporte Competitivo"

    # ----------------------------------------------------
    # 3. AUDITORÍA MARCA (DEEP DIVE)
    # ----------------------------------------------------
    elif menu == "🔍 Auditoría Marca":
        with st.sidebar:
            y_dd = st.selectbox("Año", sorted(df['AÑO'].unique(), reverse=True))
            brand_dd = st.selectbox("Marca", sorted(df[df['AÑO']==y_dd]['MARCA'].unique()))
            df_b = df[(df['AÑO'] == y_dd) & (df['MARCA'] == brand_dd)].copy()
        
        st.title(f"🔍 Auditoría: {brand_dd} ({y_dd})")
        
        if not df_b.empty:
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Volumen", f"{df_b['CANTIDAD'].sum():,.0f}")
            k2.metric("CIF Prom.", f"${df_b['CIF_UNITARIO'].mean():,.0f}")
            k3.metric("Flete Prom.", f"${df_b['FLETE_UNITARIO'].mean():,.0f}")
            k4.metric("Mix Modelos", f"{df_b['MODELO'].nunique()}")
            
            t_a, t_b = st.tabs(["Pareto (80/20)", "Logística"])
            
            with t_a:
                pareto = df_b.groupby('MODELO')['CANTIDAD'].sum().sort_values(ascending=False).reset_index()
                pareto['% Acum'] = (pareto['CANTIDAD'].cumsum() / pareto['CANTIDAD'].sum()) * 100
                pareto['Clasificación'] = np.where(pareto['% Acum'] <= 80, 'A (Vital)', 'B (Cola)')
                
                fig = px.bar(pareto, x='MODELO', y='CANTIDAD', color='Clasificación', 
                             color_discrete_map={'A (Vital)': '#27ae60', 'B (Cola)': '#95a5a6'})
                st.plotly_chart(fig, use_container_width=True)
                
            with t_b:
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("Variabilidad de Fletes")
                    fletes = df_b[(df_b['FLETE_UNITARIO'] > 50) & (df_b['FLETE_UNITARIO'] < 8000)]
                    if not fletes.empty: st.plotly_chart(px.box(fletes, y='FLETE_UNITARIO', title="Rango de Costo Logístico"), use_container_width=True)
                with c2:
                    st.subheader("Top Importadores")
                    st.dataframe(df_b.groupby('EMPRESA')['CANTIDAD'].sum().sort_values(ascending=False).head(10), use_container_width=True)

        pdf_data = df_b
        titulo_pdf = f"Auditoria {brand_dd}"

    # ==============================================================================
    # BOTÓN DE DESCARGA PDF (SIEMPRE VISIBLE SI HAY DATOS)
    # ==============================================================================
    if 'pdf_data' in locals() and not pdf_data.empty:
        st.sidebar.divider()
        st.sidebar.markdown("### 📥 Reporte")
        
        # Generación Automática en Caché (Sin botón previo)
        try:
            dict_data = pdf_data.to_dict(orient='list')
            pdf_bytes = generar_pdf_ejecutivo(dict_data, titulo_pdf, f"Generado: {pd.Timestamp.now().date()}")
            
            st.sidebar.download_button(
                label="📄 Descargar PDF Ejecutivo",
                data=pdf_bytes,
                file_name=f"Reporte_{titulo_pdf.replace(' ','_')}.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.sidebar.warning("Demasiados datos para PDF. Filtra un poco más.")

    gc.collect()

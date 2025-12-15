import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import calendar
import os
import numpy as np
import gc

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="EV Market Intelligence", 
    layout="wide", 
    page_icon="🧠",
    initial_sidebar_state="expanded"
)

# --- ESTILOS VISUALES (MINIMALISTA Y RESPONSIVE) ---
# Hemos eliminado los colores fijos para que funcione bien en Modo Oscuro y Claro
st.markdown("""
<style>
    /* Ajustes sutiles que no rompen el modo oscuro */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    /* Tabs más limpias */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 4px;
        padding: 10px 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- CARGA SEGURA DE LIBRERÍAS ---
try:
    from fpdf import FPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# --- MOTOR PDF ---
if PDF_AVAILABLE:
    class PDF(FPDF):
        def header(self):
            self.set_font('Helvetica', 'B', 14)
            self.cell(0, 10, 'Reporte de Inteligencia de Mercado', 0, 1, 'C')
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
        
        pdf.set_font("Helvetica", 'B', 16)
        pdf.cell(0, 10, clean_text(titulo), 0, 1, 'L')
        pdf.set_font("Helvetica", 'I', 10)
        pdf.cell(0, 10, f"Modo: {clean_text(modo)}", 0, 1, 'L')
        pdf.ln(5)
        
        total_vol = df['CANTIDAD'].sum()
        total_val = df['VALOR US$ CIF'].sum()
        
        pdf.set_font("Helvetica", '', 10)
        pdf.cell(0, 8, f"Volumen Total: {total_vol:,.0f}", 0, 1)
        pdf.cell(0, 8, f"Inversion Total: ${total_val/1e6:,.1f} M USD", 0, 1)
        pdf.ln(5)

        pdf.set_font("Helvetica", 'B', 12)
        pdf.cell(0, 10, "Top 10 (Volumen)", 0, 1)
        pdf.set_font("Helvetica", '', 10)
        
        agrupador = 'MODELO' if 'MODELO' in df.columns else 'MARCA'
        top = df.groupby(agrupador)['CANTIDAD'].sum().sort_values(ascending=False).head(10)
        
        for k, v in top.items():
            pdf.cell(140, 8, clean_text(k)[:50], 1)
            pdf.cell(40, 8, f"{v:,.0f}", 1, 1, 'R')

        return pdf.output(dest='S').encode('latin-1')

# --- CARGA DE DATOS ROBUSTA ---
@st.cache_data
def cargar_datos():
    archivo = "historial_lite.parquet"
    if not os.path.exists(archivo): return None
    try:
        df = pd.read_parquet(archivo)
        df.columns = df.columns.str.strip().str.upper()
        
        # 1. Normalización de Textos
        cols_str = ['MARCA', 'MODELO', 'EMPRESA', 'COMBUSTIBLE', 'CARROCERIA', 'MES']
        for c in cols_str:
            if c in df.columns: 
                df[c] = df[c].astype(str).str.strip().str.upper()
        
        if 'MARCA' in df.columns:
            df['MARCA'] = df['MARCA'].replace({'M.G.': 'MG', 'MORRIS GARAGES': 'MG', 'BYD AUTO': 'BYD'})

        # 2. Normalización de Números
        for c in ['CANTIDAD', 'VALOR US$ CIF', 'FLETE']:
            if c in df.columns: 
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        
        # 3. FIX CRÍTICO DE FECHAS (Aquí estaba el error)
        if 'FECHA' in df.columns:
            df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
            df['AÑO'] = df['FECHA'].dt.year
            df['MES_NUM'] = df['FECHA'].dt.month
        
        # Aseguramos que AÑO y MES_NUM sean enteros limpios (sin NaN ni decimales)
        df = df.dropna(subset=['AÑO', 'MES_NUM'])
        df['AÑO'] = df['AÑO'].astype(int)
        df['MES_NUM'] = df['MES_NUM'].astype(int)

        # 4. Cálculos Unitarios
        if 'VALOR US$ CIF' in df.columns:
            df['CIF_UNITARIO'] = (df['VALOR US$ CIF'] / df['CANTIDAD']).replace([np.inf, -np.inf], 0).fillna(0)
        if 'FLETE' in df.columns:
            df['FLETE_UNITARIO'] = (df['FLETE'] / df['CANTIDAD']).replace([np.inf, -np.inf], 0).fillna(0)
            
        return df
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return None

# --- SIDEBAR ---
with st.sidebar:
    st.title("🧠 Market Intelligence")
    df = cargar_datos()
    
    if df is not None:
        st.success(f"Conectado: {len(df):,.0f} Reg.")
        st.divider()
        menu = st.radio("Módulo:", 
                        ["🌍 Mercado Total", "⚔️ Benchmarking", "🔍 Deep Dive"])
        st.divider()
    else:
        st.error("No se detectan datos.")

# --- LÓGICA PRINCIPAL ---
if df is not None:
    
    # ----------------------------------------------------
    # 1. 🌍 MERCADO TOTAL (MACRO)
    # ----------------------------------------------------
    if menu == "🌍 Mercado Total":
        st.title("🌍 Visión Macro")
        
        # Filtros
        yrs = st.multiselect("Periodo", sorted(df['AÑO'].unique(), reverse=True), default=sorted(df['AÑO'].unique(), reverse=True)[:2])
        df_m = df[df['AÑO'].isin(yrs)].copy()
        
        # KPIs en Contenedores Nativos (Se ven bien en Dark/Light)
        with st.container(border=True):
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Volumen", f"{df_m['CANTIDAD'].sum():,.0f}")
            k2.metric("Valor CIF", f"${df_m['VALOR US$ CIF'].sum()/1e6:,.1f} M")
            k3.metric("Ticket Prom.", f"${df_m['CIF_UNITARIO'].mean():,.0f}")
            k4.metric("Marcas", f"{df_m['MARCA'].nunique()}")
        
        c1, c2 = st.columns([2, 1])
        
        with c1:
            st.subheader("Tendencia Temporal")
            # --- FIX DEL ERROR DE FECHAS ---
            mensual = df_m.groupby(['AÑO', 'MES_NUM'])['CANTIDAD'].sum().reset_index()
            # Método seguro para crear fechas:
            mensual['Dia'] = 1
            mensual = mensual.rename(columns={'AÑO': 'year', 'MES_NUM': 'month', 'Dia': 'day'})
            mensual['Fecha'] = pd.to_datetime(mensual[['year', 'month', 'day']])
            
            fig = px.line(mensual, x='Fecha', y='CANTIDAD', markers=True)
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.subheader("Mix Energía")
            mix = df_m.groupby('COMBUSTIBLE')['CANTIDAD'].sum().reset_index()
            fig2 = px.pie(mix, values='CANTIDAD', names='COMBUSTIBLE', hole=0.4)
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Ranking de Jugadores")
        share = df_m.groupby('MARCA')['CANTIDAD'].sum().sort_values(ascending=False).reset_index()
        share['Share %'] = (share['CANTIDAD'] / share['CANTIDAD'].sum()) * 100
        st.dataframe(share.head(15).style.format({'Share %': '{:.1f}%'}), use_container_width=True)

    # ----------------------------------------------------
    # 2. ⚔️ BENCHMARKING (COMPARATIVO)
    # ----------------------------------------------------
    elif menu == "⚔️ Benchmarking":
        st.title("⚔️ Comparativo")
        
        with st.sidebar:
            st.markdown("### Configuración")
            yrs_b = st.multiselect("Años", sorted(df['AÑO'].unique(), reverse=True), default=sorted(df['AÑO'].unique(), reverse=True)[:1])
            df_curr = df[df['AÑO'].isin(yrs_b)]
            
            # Botones inteligentes de selección
            mks_avail = sorted(df_curr['MARCA'].unique())
            if st.checkbox("Seleccionar Todas las Marcas", value=False):
                mks = mks_avail
            else:
                default_mks = df_curr['MARCA'].value_counts().head(3).index.tolist()
                mks = st.multiselect("Competidores", mks_avail, default=default_mks)

        df_c = df_curr[df_curr['MARCA'].isin(mks)].copy()
        
        if not df_c.empty:
            t1, t2, t3 = st.tabs(["📊 Volumen", "💰 Precios", "🕵️ Fuga (Gris)"])
            
            with t1:
                fig = px.bar(df_c.groupby(['MARCA', 'AÑO'])['CANTIDAD'].sum().reset_index(), 
                             x='MARCA', y='CANTIDAD', color='AÑO', barmode='group', text_auto=True)
                st.plotly_chart(fig, use_container_width=True)
            
            with t2:
                # Filtro outliers visual
                df_p = df_c[(df_c['CIF_UNITARIO'] > 2000) & (df_c['CIF_UNITARIO'] < 150000)]
                fig_box = px.box(df_p, x='MARCA', y='CIF_UNITARIO', color='MARCA')
                st.plotly_chart(fig_box, use_container_width=True)

            with t3:
                # Algoritmo Rápido Vectorizado
                gb = df_c.groupby(['MARCA', 'EMPRESA'])['CANTIDAD'].sum().reset_index()
                oficiales = gb.sort_values(['MARCA','CANTIDAD'], ascending=[True, False]).drop_duplicates('MARCA')
                oficiales = oficiales.rename(columns={'EMPRESA':'OFICIAL_NAME'})[['MARCA','OFICIAL_NAME']]
                
                df_c = df_c.merge(oficiales, on='MARCA', how='left')
                df_c['CANAL'] = np.where(df_c['EMPRESA'] == df_c['OFICIAL_NAME'], 'OFICIAL', 'GRIS')
                
                resumen = df_c.groupby(['MARCA', 'CANAL'])['CANTIDAD'].sum().unstack().fillna(0).reset_index()
                if 'GRIS' not in resumen.columns: resumen['GRIS'] = 0
                if 'OFICIAL' not in resumen.columns: resumen['OFICIAL'] = 0
                
                fig_g = px.bar(resumen, x='MARCA', y=['OFICIAL', 'GRIS'], title="Oficial vs Gris", 
                               color_discrete_map={'OFICIAL':'#2ecc71', 'GRIS':'#95a5a6'})
                st.plotly_chart(fig_g, use_container_width=True)

    # ----------------------------------------------------
    # 3. 🔍 DEEP DIVE (MARCA)
    # ----------------------------------------------------
    elif menu == "🔍 Deep Dive":
        with st.sidebar:
            y_dd = st.selectbox("Año Fiscal", sorted(df['AÑO'].unique(), reverse=True))
            df_y = df[df['AÑO'] == y_dd]
            brand_dd = st.selectbox("Marca", sorted(df_y['MARCA'].unique()))
            df_b = df_y[df_y['MARCA'] == brand_dd].copy()
        
        st.title(f"🔍 Auditoría: {brand_dd}")
        
        if not df_b.empty:
            with st.container(border=True):
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Unidades", f"{df_b['CANTIDAD'].sum():,.0f}")
                k2.metric("CIF Prom.", f"${df_b['CIF_UNITARIO'].mean():,.0f}")
                k3.metric("Flete Prom.", f"${df_b['FLETE_UNITARIO'].mean():,.0f}")
                k4.metric("Modelos", f"{df_b['MODELO'].nunique()}")
            
            tab_a, tab_b, tab_c = st.tabs(["Pareto", "Proyección", "Logística"])
            
            with tab_a:
                pareto = df_b.groupby('MODELO')['CANTIDAD'].sum().sort_values(ascending=False).reset_index()
                pareto['Acum'] = pareto['CANTIDAD'].cumsum()
                pareto['%'] = (pareto['Acum'] / pareto['CANTIDAD'].sum()) * 100
                
                fig_p = go.Figure()
                fig_p.add_trace(go.Bar(x=pareto['MODELO'], y=pareto['CANTIDAD'], name='Volumen'))
                fig_p.add_trace(go.Scatter(x=pareto['MODELO'], y=pareto['%'], yaxis='y2', name='%', line=dict(color='red')))
                fig_p.update_layout(yaxis2=dict(overlaying='y', side='right', range=[0, 110]))
                st.plotly_chart(fig_p, use_container_width=True)
                
            with tab_b:
                mensual = df_b.groupby('MES_NUM')['CANTIDAD'].sum().reset_index()
                # FIX FECHAS PARA GRÁFICO
                mensual['year'] = y_dd
                mensual['day'] = 1
                mensual = mensual.rename(columns={'MES_NUM':'month'})
                mensual['Fecha'] = pd.to_datetime(mensual[['year', 'month', 'day']])
                
                if len(mensual) > 1:
                    try:
                        fig_tr = px.scatter(mensual, x='Fecha', y='CANTIDAD', trendline="ols", trendline_color_override="red", title="Forecast")
                        fig_tr.update_traces(mode='lines+markers')
                        st.plotly_chart(fig_tr, use_container_width=True)
                    except:
                        st.line_chart(mensual.set_index('Fecha')['CANTIDAD'])
                else: st.warning("Datos insuficientes.")

            with tab_c:
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("Variabilidad de Fletes")
                    fletes = df_b[(df_b['FLETE_UNITARIO'] > 100) & (df_b['FLETE_UNITARIO'] < 8000)]
                    if not fletes.empty:
                        fig_f = px.box(fletes, x='MES_NUM', y='FLETE_UNITARIO')
                        st.plotly_chart(fig_f, use_container_width=True)
                    else: st.info("Sin datos.")
                with c2:
                    st.subheader("Importadores")
                    st.dataframe(df_b.groupby('EMPRESA')['CANTIDAD'].sum().sort_values(ascending=False), use_container_width=True)

    # ----------------------------------------------------
    # BOTÓN PDF GLOBAL
    # ----------------------------------------------------
    if PDF_AVAILABLE:
        st.sidebar.divider()
        if menu == "🌍 Mercado Total": pdf_data = df_m if 'df_m' in locals() else df.head(50)
        elif menu == "⚔️ Benchmarking": pdf_data = df_c if 'df_c' in locals() else df.head(50)
        else: pdf_data = df_b if 'df_b' in locals() else df.head(50)
        
        if st.sidebar.button("📄 Generar PDF"):
            try:
                # Convertimos a dict para que el caché funcione rápido y no falle
                data_dict = pdf_data.to_dict(orient='list')
                pdf_bytes = generar_pdf(data_dict, f"Reporte: {menu}", menu)
                st.sidebar.download_button("💾 Descargar", pdf_bytes, "Reporte.pdf", "application/pdf")
            except Exception as e:
                st.sidebar.warning("Reduce el rango de fechas para generar el PDF.")

    gc.collect()

else:
    st.info("Conectando con GitHub...")

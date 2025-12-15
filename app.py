import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import calendar
import os
import numpy as np
import gc # Garbage Collector para liberar memoria
from fpdf import FPDF

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="EV Market Intelligence", 
    layout="wide", 
    page_icon="⚡",
    initial_sidebar_state="expanded"
)

# --- ESTILOS VISUALES ---
st.markdown("""
<style>
    .main {background-color: #f4f6f9;}
    h1, h2, h3 {font-family: 'Helvetica', sans-serif; color: #1e3799;}
    .metric-card {background-color: white; border-left: 5px solid #1e3799; padding: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);}
    /* Optimización para evitar crash visual */
    .stPlotlyChart {min-height: 400px;}
</style>
""", unsafe_allow_html=True)

# --- CARGA SEGURA DE LIBRERÍAS ---
try:
    from fpdf import FPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# --- FUNCIONES PDF OPTIMIZADAS (CON CACHÉ) ---
if PDF_AVAILABLE:
    class PDF(FPDF):
        def header(self):
            self.set_font('Helvetica', 'B', 15)
            self.cell(0, 10, 'Reporte de Inteligencia de Mercado - EV', 0, 1, 'C')
            self.ln(5)
        def footer(self):
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 8)
            self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    def clean_text(text):
        try: return str(text).encode('latin-1', 'replace').decode('latin-1')
        except: return str(text)

    # USAMOS CACHÉ AQUÍ PARA NO REVENTAR LA MEMORIA
    @st.cache_data(show_spinner=False)
    def generar_pdf_nativo(df_dict, titulo_reporte):
        # Reconstruimos DataFrame desde diccionario para el caché
        df_filtrado = pd.DataFrame(df_dict)
        
        pdf = PDF()
        pdf.add_page()
        pdf.set_font("Helvetica", 'B', 14)
        pdf.cell(0, 10, f"Analisis: {clean_text(titulo_reporte)}", 0, 1, 'L')
        pdf.ln(5)
        
        # KPIs
        total_unidades = df_filtrado['CANTIDAD'].sum()
        total_inversion = df_filtrado['VALOR US$ CIF'].sum()
        precio_prom = total_inversion / total_unidades if total_unidades > 0 else 0
        
        pdf.set_font("Helvetica", '', 10)
        pdf.cell(0, 8, f"Total Unidades: {total_unidades:,.0f}", 0, 1)
        pdf.cell(0, 8, f"Inversion Total: ${total_inversion/1e6:,.2f} M USD", 0, 1)
        pdf.cell(0, 8, f"Precio Promedio: ${precio_prom:,.0f}", 0, 1)
        pdf.ln(10)

        # Top Marcas
        pdf.set_font("Helvetica", 'B', 12)
        pdf.cell(0, 10, "Top 5 Marcas (Volumen)", 0, 1, 'L')
        pdf.set_font("Helvetica", '', 10)
        
        top_marcas = df_filtrado.groupby('MARCA')['CANTIDAD'].sum().sort_values(ascending=False).head(5)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(100, 10, "Marca", 1, 0, 'C', 1)
        pdf.cell(50, 10, "Unidades", 1, 1, 'C', 1)
        for marca, cant in top_marcas.items():
            pdf.cell(100, 10, clean_text(marca), 1)
            pdf.cell(50, 10, f"{cant:,.0f}", 1, 1, 'R')
        pdf.ln(10)

        return pdf.output(dest='S').encode('latin-1')

# --- CARGA DE DATOS ---
@st.cache_data
def cargar_datos_automatico():
    archivo = "historial_lite.parquet"
    if not os.path.exists(archivo): return None, "Falta archivo"
    try:
        df = pd.read_parquet(archivo)
        df.columns = df.columns.str.strip().str.upper()
        # Limpieza rápida Vectorizada
        if 'MARCA' in df.columns:
            df['MARCA'] = df['MARCA'].astype(str).str.upper().replace({'M.G.': 'MG', 'MORRIS GARAGES': 'MG', 'BYD AUTO': 'BYD'})
        
        cols_str = ['MODELO', 'EMPRESA', 'COMBUSTIBLE', 'CARROCERIA']
        for c in cols_str:
            if c in df.columns: df[c] = df[c].astype(str).str.strip().str.upper()
            
        if 'CARROCERIA' not in df.columns: df['CARROCERIA'] = 'NO DEFINIDO'
        
        for c in ['CANTIDAD', 'VALOR US$ CIF', 'FLETE']:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
            
        if 'FECHA' in df.columns:
            df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
            df['AÑO'] = df['FECHA'].dt.year
            df['MES_NUM'] = df['FECHA'].dt.month
            
        if 'VALOR US$ CIF' in df.columns and 'CANTIDAD' in df.columns:
            df['CIF_UNITARIO'] = (df['VALOR US$ CIF'] / df['CANTIDAD']).replace([np.inf, -np.inf], 0).fillna(0)
            
        if 'FLETE' in df.columns and 'CANTIDAD' in df.columns:
            df['FLETE_UNITARIO'] = (df['FLETE'] / df['CANTIDAD']).replace([np.inf, -np.inf], 0).fillna(0)

        return df, "OK"
    except Exception as e: return None, str(e)

# --- INICIO DE APP (CON PROTECCIÓN DE ERRORES) ---
try:
    with st.sidebar:
        st.title("💼 EV Intelligence")
        df, msg = cargar_datos_automatico()
        if df is not None:
            st.success(f"Online: {len(df):,.0f} regs")
            st.divider()
            modo = st.radio("Menú:", ["⚔️ Comparativo", "🔍 Detalle"], index=0)
        else:
            st.error(f"Error: {msg}")

    if df is not None:
        # === MODO 1: COMPARATIVO ===
        if modo == "⚔️ Comparativo":
            with st.sidebar:
                yrs_all = sorted(df['AÑO'].dropna().unique().astype(int), reverse=True)
                chk_yr = st.checkbox("Todos los Años", value=True)
                yrs = yrs_all if chk_yr else st.multiselect("Años", yrs_all, default=yrs_all[:1])
                
                # Filtrado ligero
                mask_y = df['AÑO'].isin(yrs)
                df_y = df[mask_y]
                
                mks_all = sorted(df_y['MARCA'].unique())
                chk_mk = st.checkbox("Todas las Marcas", value=True)
                mks = mks_all if chk_mk else st.multiselect("Marcas", mks_all, default=mks_all[:3])
                
                st.divider()
                st.markdown("### 📥 Reportes")

            # Filtro Final
            mask_final = (df['AÑO'].isin(yrs)) & (df['MARCA'].isin(mks))
            df_f = df[mask_final].copy() # Copy esencial aquí
            
            # --- CÁLCULO VECTORIZADO DE MERCADO GRIS (ESTO EVITA EL CRASH) ---
            if not df_f.empty:
                # 1. Calculamos totales por Marca/Empresa
                gb = df_f.groupby(['MARCA', 'EMPRESA'])['CANTIDAD'].sum().reset_index()
                # 2. Ordenamos para que el mayor quede arriba
                gb = gb.sort_values(['MARCA', 'CANTIDAD'], ascending=[True, False])
                # 3. Nos quedamos solo con el primero de cada marca (el Oficial)
                oficiales = gb.drop_duplicates('MARCA')[['MARCA', 'EMPRESA']].rename(columns={'EMPRESA': 'OFICIAL_NAME'})
                
                # 4. Cruzamos (Merge) los datos originales con la tabla de oficiales
                # Esto es 100 veces más rápido que un bucle for o apply
                df_f = df_f.merge(oficiales, on='MARCA', how='left')
                
                # 5. Etiquetamos
                df_f['TIPO_IMPORTADOR'] = np.where(df_f['EMPRESA'] == df_f['OFICIAL_NAME'], 'OFICIAL', 'GRIS')

                # --- PDF CACHÉ ---
                if PDF_AVAILABLE:
                    try:
                        # Pasamos df como diccionario para que Streamlit pueda hashearlo rápido
                        pdf_bytes = generar_pdf_nativo(df_f.to_dict(orient='list'), "Comparativo Global")
                        with st.sidebar:
                            st.download_button("📄 Descargar PDF", pdf_bytes, "Reporte_Global.pdf", "application/pdf")
                    except Exception: pass

                st.title("⚔️ Panorama Competitivo")
                
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.subheader("Mercado Gris (Tendencia)")
                    trend = df_f.groupby(['AÑO', 'TIPO_IMPORTADOR'])['CANTIDAD'].sum().unstack().fillna(0)
                    trend['Total'] = trend.sum(axis=1)
                    if 'GRIS' in trend.columns:
                        trend['% Gris'] = (trend['GRIS'] / trend['Total']) * 100
                    else: trend['% Gris'] = 0
                    
                    trend = trend.reset_index()
                    fig = px.bar(trend, x='AÑO', y=[c for c in ['OFICIAL', 'GRIS'] if c in trend.columns], 
                                 title="Oficial vs Gris", color_discrete_map={'OFICIAL': '#27AE60', 'GRIS': '#95A5A6'})
                    fig.add_trace(go.Scatter(x=trend['AÑO'], y=trend['% Gris'], name='% Fuga', yaxis='y2', line=dict(color='red', width=3)))
                    fig.update_layout(yaxis2=dict(overlaying='y', side='right', range=[0, 100], title="% Fuga"))
                    st.plotly_chart(fig, use_container_width=True)
                
                with c2:
                    st.subheader("Top Gris")
                    if 'GRIS' in df_f['TIPO_IMPORTADOR'].unique():
                        top_gris = df_f[df_f['TIPO_IMPORTADOR']=='GRIS'].groupby('EMPRESA')['CANTIDAD'].sum().sort_values(ascending=False).head(10).reset_index()
                        st.dataframe(top_gris, use_container_width=True, hide_index=True)
                    else: st.success("Mercado Limpio.")

        # === MODO 2: DETALLE ===
        elif modo == "🔍 Detalle":
            with st.sidebar:
                y = st.selectbox("Año", sorted(df['AÑO'].dropna().unique().astype(int), reverse=True))
                df_y = df[df['AÑO']==y] # Sin copy para ahorrar memoria
                
                m = st.selectbox("Marca", ["TODO EL MERCADO"] + sorted(df_y['MARCA'].unique()))
                if m != "TODO EL MERCADO": df_y = df_y[df_y['MARCA']==m]
                
                comb = st.multiselect("Combustible", sorted(df_y['COMBUSTIBLE'].unique()), default=sorted(df_y['COMBUSTIBLE'].unique()))
                
                # Aquí sí hacemos copy porque es el dataset final pequeño
                df_d = df_y[df_y['COMBUSTIBLE'].isin(comb)].copy()
                
                st.divider()
                if not df_d.empty and PDF_AVAILABLE:
                    pdf_bytes_d = generar_pdf_nativo(df_d.to_dict(orient='list'), f"Detalle {m}")
                    st.download_button("📄 Descargar PDF", pdf_bytes_d, f"Reporte_{m}.pdf", "application/pdf")

            if not df_d.empty:
                st.title(f"🔍 Análisis: {m}")
                k1, k2, k3 = st.columns(3)
                k1.metric("Volumen", f"{df_d['CANTIDAD'].sum():,.0f}")
                k2.metric("Precio CIF", f"${df_d['CIF_UNITARIO'].mean():,.0f}")
                k3.metric("Total USD", f"${df_d['VALOR US$ CIF'].sum()/1e6:,.1f} M")
                
                t1, t2 = st.tabs(["Tendencia", "Logística"])
                
                with t1:
                    mensual = df_d.groupby('MES_NUM')['CANTIDAD'].sum().reset_index()
                    if len(mensual) > 1:
                        try:
                            fig = px.scatter(mensual, x='MES_NUM', y='CANTIDAD', trendline="ols", trendline_color_override="red", title="Proyección")
                            fig.update_traces(mode='lines+markers')
                            fig.update_xaxes(tickmode='array', tickvals=list(range(1,13)), ticktext=[calendar.month_abbr[i] for i in range(1,13)])
                            st.plotly_chart(fig, use_container_width=True)
                        except: st.plotly_chart(px.line(mensual, x='MES_NUM', y='CANTIDAD'), use_container_width=True)
                
                with t2:
                    df_flt = df_d[(df_d['FLETE_UNITARIO'] > 50) & (df_d['FLETE_UNITARIO'] < 8000)]
                    if not df_flt.empty:
                        stats = df_flt.groupby('MES_NUM')['FLETE_UNITARIO'].agg(['min', 'max', 'mean']).reset_index()
                        stats['Mes'] = stats['MES_NUM'].apply(lambda x: calendar.month_abbr[int(x)])
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(x=stats['Mes'], y=stats['max'], mode='lines', showlegend=False))
                        fig.add_trace(go.Scatter(x=stats['Mes'], y=stats['min'], mode='lines', fill='tonexty', fillcolor='rgba(255, 165, 0, 0.2)'))
                        fig.add_trace(go.Scatter(x=stats['Mes'], y=stats['mean'], mode='lines+markers', line=dict(color='orange', width=3)))
                        st.plotly_chart(fig, use_container_width=True)
                    else: st.info("Sin datos de fletes.")
            else: st.warning("Sin datos.")

    # Liberar memoria al final de cada ejecución
    gc.collect()

except Exception as e:
    st.error(f"Se ha producido un error inesperado: {e}")
    st.info("Intenta recargar la página.")

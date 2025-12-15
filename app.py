import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import calendar
import os
import numpy as np
from fpdf import FPDF

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="EV Market Intelligence", 
    layout="wide", 
    page_icon="💼",
    initial_sidebar_state="expanded"
)

# --- ESTILOS VISUALES ---
st.markdown("""
<style>
    .main {background-color: #f4f6f9;}
    h1, h2, h3 {font-family: 'Arial', sans-serif; color: #1e3799;}
    .metric-card {background-color: white; border-left: 5px solid #1e3799; padding: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);}
    div[data-testid="stMetricValue"] {font-size: 24px; color: #1e3799;}
</style>
""", unsafe_allow_html=True)

# --- MOTOR DE REPORTE PDF (BLINDADO) ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Reporte de Inteligencia de Mercado - EV', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

def clean_text(text):
    """Limpia el texto para evitar errores de caracteres raros (emojis/chinos) en el PDF"""
    try:
        return str(text).encode('latin-1', 'replace').decode('latin-1')
    except:
        return str(text)

def generar_pdf_nativo(df_filtrado, titulo_reporte):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # 1. Título y Resumen
    pdf.set_font("Arial", 'B', 14)
    # Usamos clean_text para asegurar que el título no rompa el PDF
    pdf.cell(0, 10, f"Analisis: {clean_text(titulo_reporte)}", 0, 1, 'L')
    pdf.ln(5)
    
    # KPIs Generales
    total_unidades = df_filtrado['CANTIDAD'].sum()
    total_inversion = df_filtrado['VALOR US$ CIF'].sum()
    precio_prom = total_inversion / total_unidades if total_unidades > 0 else 0
    
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 8, f"Total Unidades Importadas: {total_unidades:,.0f}", 0, 1)
    pdf.cell(0, 8, f"Inversion Total CIF: ${total_inversion/1e6:,.2f} Millones USD", 0, 1)
    pdf.cell(0, 8, f"Precio Promedio CIF: ${precio_prom:,.0f}", 0, 1)
    pdf.ln(10)

    # 2. Tabla Top Marcas (Texto)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Top 5 Marcas por Volumen", 0, 1, 'L')
    pdf.set_font("Arial", '', 10)
    
    top_marcas = df_filtrado.groupby('MARCA')['CANTIDAD'].sum().sort_values(ascending=False).head(5)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(100, 10, "Marca", 1, 0, 'C', 1)
    pdf.cell(50, 10, "Unidades", 1, 1, 'C', 1)
    
    for marca, cant in top_marcas.items():
        pdf.cell(100, 10, clean_text(marca), 1)
        pdf.cell(50, 10, f"{cant:,.0f}", 1, 1, 'R')
    pdf.ln(10)

    # 3. Análisis Mercado Gris
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Analisis de Fuga (Mercado Gris)", 0, 1, 'L')
    pdf.set_font("Arial", '', 10)
    
    # Lógica de cálculo
    mapa_oficiales = {}
    marcas_unicas = df_filtrado['MARCA'].unique()
    for m in marcas_unicas:
        d = df_filtrado[df_filtrado['MARCA'] == m]
        if not d.empty: mapa_oficiales[m] = d.groupby('EMPRESA')['CANTIDAD'].sum().idxmax()
    
    df_filtrado['TIPO'] = df_filtrado.apply(lambda x: 'OFICIAL' if x['EMPRESA'] == mapa_oficiales.get(x['MARCA']) else 'GRIS', axis=1)
    vol_gris = df_filtrado[df_filtrado['TIPO']=='GRIS']['CANTIDAD'].sum()
    pct_gris = (vol_gris / total_unidades) * 100 if total_unidades > 0 else 0
    
    pdf.multi_cell(0, 8, f"Del volumen total analizado, se detectaron {vol_gris:,.0f} unidades ingresadas por Mercado Gris, lo que representa un {pct_gris:.1f}% de fuga.")
    pdf.ln(5)
    
    # Tabla Top Gris
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, "Top Importadores No Oficiales:", 0, 1)
    top_gris = df_filtrado[df_filtrado['TIPO']=='GRIS'].groupby('EMPRESA')['CANTIDAD'].sum().sort_values(ascending=False).head(5)
    
    for emp, cant in top_gris.items():
        # Limpieza agresiva de nombre de empresa
        emp_clean = clean_text(str(emp))[:40] 
        pdf.set_font("Arial", '', 9)
        pdf.cell(140, 8, f"- {emp_clean}", 0, 0)
        pdf.cell(30, 8, f"{cant:,.0f} unds", 0, 1, 'R')

    # Guardar en memoria
    return pdf.output(dest='S').encode('latin-1')

# --- CARGA DE DATOS ---
@st.cache_data
def cargar_datos_automatico():
    archivo_objetivo = "historial_lite.parquet"
    if not os.path.exists(archivo_objetivo):
        return None, f"❌ ERROR: No encuentro '{archivo_objetivo}' en GitHub."
    try:
        df = pd.read_parquet(archivo_objetivo)
        df.columns = df.columns.str.strip().str.upper()
        
        # Limpieza básica
        cols_txt = ['MARCA', 'MODELO', 'EMPRESA', 'COMBUSTIBLE', 'MES', 'CARROCERIA']
        for c in cols_txt:
            if c in df.columns: 
                df[c] = df[c].astype(str).str.strip().str.upper()
                if c == 'MARCA': df[c] = df[c].replace(['M.G.', 'MORRIS GARAGES'], 'MG').replace(['BYD AUTO'], 'BYD')
        
        if 'CARROCERIA' not in df.columns: df['CARROCERIA'] = 'NO DEFINIDO'

        for c in ['CANTIDAD', 'VALOR US$ CIF', 'FLETE']:
            if c in df.columns:
                if df[c].dtype == 'object':
                    df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce').fillna(0)
                else:
                    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        
        if 'FECHA' in df.columns:
            df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
            df['AÑO'] = df['FECHA'].dt.year
            df['MES_NUM'] = df['FECHA'].dt.month
        
        if 'VALOR US$ CIF' in df.columns and 'CANTIDAD' in df.columns:
            df['CIF_UNITARIO'] = df['VALOR US$ CIF'] / df['CANTIDAD']
            df['CIF_UNITARIO'] = df['CIF_UNITARIO'].replace([np.inf, -np.inf], 0).fillna(0)
            
        if 'FLETE' in df.columns and 'CANTIDAD' in df.columns:
            df['FLETE_UNITARIO'] = df['FLETE'] / df['CANTIDAD']
            df['FLETE_UNITARIO'] = df['FLETE_UNITARIO'].replace([np.inf, -np.inf], 0).fillna(0)

        return df, "OK"
    except Exception as e:
        return None, f"❌ Error: {str(e)}"

# --- SIDEBAR ---
with st.sidebar:
    st.title("💼 EV Intelligence")
    df, mensaje = cargar_datos_automatico()
    
    if df is not None:
        st.success(f"✅ Conectado ({len(df):,.0f} regs)")
        st.divider()
        modo = st.radio("Navegación:", ["⚔️ Comparativo Global", "🔍 Deep Dive (Detalle)"], index=0)
    else:
        st.error(mensaje)

# --- LÓGICA PRINCIPAL ---
if df is not None:
    
    # === MODO 1: COMPARATIVO ===
    if modo == "⚔️ Comparativo Global":
        with st.sidebar:
            st.subheader("Filtros")
            # Selección TOTAL por defecto
            yrs_all = sorted(df['AÑO'].dropna().unique().astype(int), reverse=True)
            chk_yr = st.checkbox("Todos los Años", value=True)
            yrs = yrs_all if chk_yr else st.multiselect("Años", yrs_all, default=yrs_all[:1])
            
            df_y = df[df['AÑO'].isin(yrs)]
            
            mks_all = sorted(df_y['MARCA'].unique())
            chk_mk = st.checkbox("Todas las Marcas", value=True)
            mks = mks_all if chk_mk else st.multiselect("Marcas", mks_all, default=mks_all[:3])
            
            st.divider()
            st.markdown("### 📥 Descargas")
            
        df_f = df[(df['AÑO'].isin(yrs)) & (df['MARCA'].isin(mks))].copy()
        
        # --- GENERACIÓN DEL PDF EN TIEMPO REAL ---
        if not df_f.empty:
            # Ponemos el botón en el sidebar
            with st.sidebar:
                # Generamos el PDF usando la función blindada
                pdf_bytes = generar_pdf_nativo(df_f, "Comparativo Global")
                st.download_button(
                    label="📄 Descargar Reporte PDF",
                    data=pdf_bytes,
                    file_name="Reporte_Ejecutivo.pdf",
                    mime="application/pdf"
                )

            st.title("⚔️ Panorama Competitivo")
            
            # LÓGICA MERCADO GRIS (SOLICITUD: LIDER = OFICIAL)
            mapa_oficiales = {}
            for m in mks:
                d = df_f[df_f['MARCA'] == m]
                if not d.empty: 
                    # El importador #1 es el OFICIAL
                    mapa_oficiales[m] = d.groupby('EMPRESA')['CANTIDAD'].sum().idxmax()
            
            df_f['TIPO_IMPORTADOR'] = df_f.apply(lambda x: 'OFICIAL' if x['EMPRESA'] == mapa_oficiales.get(x['MARCA']) else 'GRIS', axis=1)

            # GRÁFICOS
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader("Tendencia de Fuga (Gris)")
                # Gráfico Evolutivo de % Gris
                trend = df_f.groupby(['AÑO', 'TIPO_IMPORTADOR'])['CANTIDAD'].sum().unstack().fillna(0)
                trend['Total'] = trend['OFICIAL'] + trend['GRIS']
                trend['% Gris'] = (trend['GRIS'] / trend['Total']) * 100
                trend = trend.reset_index()
                
                fig = px.bar(trend, x='AÑO', y=['OFICIAL', 'GRIS'], title="Oficial vs Gris por Año", 
                             color_discrete_map={'OFICIAL': '#27AE60', 'GRIS': '#95A5A6'})
                fig.add_trace(go.Scatter(x=trend['AÑO'], y=trend['% Gris'], name='% Fuga', yaxis='y2', line=dict(color='red', width=3)))
                fig.update_layout(yaxis2=dict(overlaying='y', side='right', range=[0, 100], title="% Fuga"))
                st.plotly_chart(fig, use_container_width=True)
                
            with c2:
                st.subheader("Top Importadores Gris")
                gris_top = df_f[df_f['TIPO_IMPORTADOR']=='GRIS'].groupby('EMPRESA')['CANTIDAD'].sum().sort_values(ascending=False).head(10).reset_index()
                st.dataframe(gris_top.style.background_gradient(cmap="Reds"), use_container_width=True, hide_index=True)

    # === MODO 2: DEEP DIVE ===
    elif modo == "🔍 Deep Dive (Detalle)":
        with st.sidebar:
            y = st.selectbox("Año Fiscal", sorted(df['AÑO'].dropna().unique().astype(int), reverse=True))
            df_y = df[df['AÑO']==y].copy()
            
            m = st.selectbox("Marca", ["TODO EL MERCADO"] + sorted(df_y['MARCA'].unique()))
            if m != "TODO EL MERCADO": df_y = df_y[df_y['MARCA']==m]
            
            comb = st.multiselect("⛽ Combustible", sorted(df_y['COMBUSTIBLE'].unique()), default=sorted(df_y['COMBUSTIBLE'].unique()))
            df_d = df_y[df_y['COMBUSTIBLE'].isin(comb)].copy()
            
            st.divider()
            # Botón de Descarga PDF para esta vista
            if not df_d.empty:
                # Usamos la función blindada
                pdf_bytes_d = generar_pdf_nativo(df_d, f"Detalle {m} ({y})")
                st.download_button(label="📄 Descargar Reporte PDF", data=pdf_bytes_d, file_name=f"Reporte_{m}_{y}.pdf", mime="application/pdf")

        if not df_d.empty:
            st.title(f"🔍 Análisis Profundo: {m}")
            
            # VISUALES DIDÁCTICOS (SOLICITUD: MÁS CLAROS)
            k1, k2, k3 = st.columns(3)
            k1.metric("📦 Volumen Total", f"{df_d['CANTIDAD'].sum():,.0f} autos", delta="Total Importado")
            k2.metric("💵 Costo CIF Promedio", f"${df_d['CIF_UNITARIO'].mean():,.0f}", delta="Precio Promedio")
            k3.metric("🚨 Nivel de Fuga", "Calculando...", delta_color="inverse")

            st.markdown("---")
            
            t1, t2, t3 = st.tabs(["📈 Tendencia Explicada", "🚢 Logística Visual", "⚖️ 80/20 Clave"])
            
            with t1:
                st.subheader("¿La marca está creciendo o cayendo?")
                mensual = df_d.groupby('MES_NUM')['CANTIDAD'].sum().reset_index()
                if len(mensual) > 1:
                    try:
                        fig = px.scatter(mensual, x='MES_NUM', y='CANTIDAD', trendline="ols", title="Dirección del Mercado", trendline_color_override="red")
                        fig.update_traces(mode='lines+markers', marker=dict(size=10))
                        fig.update_xaxes(tickmode='array', tickvals=list(range(1,13)), ticktext=[calendar.month_abbr[i] for i in range(1,13)])
                        st.plotly_chart(fig, use_container_width=True)
                        st.success("✅ **Lectura Fácil:** La línea roja indica el futuro probable. Si apunta arriba, compra más stock. Si apunta abajo, cuidado.")
                    except:
                        st.plotly_chart(px.line(mensual, x='MES_NUM', y='CANTIDAD'), use_container_width=True)
                else: st.warning("Datos insuficientes para predecir.")

            with t2:
                st.subheader("Rango de Negociación de Fletes")
                df_flt = df_d[(df_d['FLETE_UNITARIO'] > 50) & (df_d['FLETE_UNITARIO'] < 8000)]
                if not df_flt.empty:
                    stats = df_flt.groupby('MES_NUM')['FLETE_UNITARIO'].agg(['min', 'max', 'mean']).reset_index()
                    stats['Mes'] = stats['MES_NUM'].apply(lambda x: calendar.month_abbr[int(x)])
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=stats['Mes'], y=stats['max'], mode='lines', line=dict(width=0), showlegend=False))
                    fig.add_trace(go.Scatter(x=stats['Mes'], y=stats['min'], mode='lines', fill='tonexty', fillcolor='rgba(255, 165, 0, 0.2)', name='Zona de Precio'))
                    fig.add_trace(go.Scatter(x=stats['Mes'], y=stats['mean'], mode='lines+markers', line=dict(color='orange', width=3), name='Costo Real'))
                    st.plotly_chart(fig, use_container_width=True)
                    st.info("ℹ️ **Didáctico:** La zona sombreada es la diferencia entre el flete más barato y el más caro. Trata de mantenerte en la parte baja de la sombra.")

            with t3:
                st.subheader("Modelos que sostienen el negocio")
                pareto = df_d.groupby('MODELO')['CANTIDAD'].sum().sort_values(ascending=False).reset_index()
                pareto['%'] = (pareto['CANTIDAD'].cumsum() / pareto['CANTIDAD'].sum()) * 100
                
                # Colores semánticos
                pareto['Color'] = np.where(pareto['%'] <= 80, '#2ECC71', '#95A5A6') # Verde vital, Gris resto
                
                fig = go.Figure()
                fig.add_trace(go.Bar(x=pareto['MODELO'], y=pareto['CANTIDAD'], marker_color=pareto['Color'], name='Unidades'))
                st.plotly_chart(fig, use_container_width=True)
                st.caption("🟢 **Verde:** Modelos Vitales (80% ventas) | ⚪ **Gris:** Modelos de Relleno")

else:
    st.info("Conectando con GitHub...")

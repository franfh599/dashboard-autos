import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import calendar
import os

# --- CONFIGURACIÓN ---
st.set_page_config(
    page_title="EV Market Intelligence", 
    layout="wide", 
    page_icon="📊",
    initial_sidebar_state="expanded"
)

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .main {background-color: #f8f9fa;}
    h1, h2, h3 {font-family: 'Segoe UI', sans-serif; color: #2c3e50;}
    @media (max-width: 768px) { .block-container {padding: 1rem 0.5rem !important;} h1 {font-size: 1.5rem !important;} }
    @media print {
        [data-testid="stSidebar"], [data-testid="stHeader"], .stDeployButton, footer, .no-print {display: none !important;}
        body, .stApp {background-color: white !important; color: black !important;}
        .block-container {max-width: 100% !important; padding: 0 !important; margin: 0 !important;}
        body {zoom: 65%;}
    }
</style>
""", unsafe_allow_html=True)

# --- CARGA DE DATOS OPTIMIZADA (PARQUET) ---
@st.cache_data
def cargar_datos(archivo):
    try:
        # Detectamos si es Excel o Parquet
        if archivo.name.endswith('.parquet'):
            df = pd.read_parquet(archivo)
        else:
            try:
                df = pd.read_excel(archivo, sheet_name='2019-2025')
            except:
                df = pd.read_excel(archivo)

        # Limpieza Estándar
        df.columns = df.columns.str.strip().str.upper()
        cols_txt = ['MARCA', 'MODELO', 'EMPRESA', 'COMBUSTIBLE', 'MES', 'CARROCERIA', 'ESTILO']
        for c in cols_txt:
            if c in df.columns: 
                df[c] = df[c].astype(str).str.strip().str.upper()
                if c == 'MARCA':
                    df[c] = df[c].replace(['M.G.', 'MORRIS GARAGES', 'M. G.'], 'MG').replace(['BYD AUTO'], 'BYD')

        if 'CARROCERIA' not in df.columns:
            df['CARROCERIA'] = df['ESTILO'] if 'ESTILO' in df.columns else 'NO DEFINIDO'

        for c in ['CANTIDAD', 'VALOR US$ CIF', 'FLETE']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce').fillna(0)
        
        if 'FECHA' in df.columns:
            df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
            df['AÑO'] = df['FECHA'].dt.year
            df['MES_NUM'] = df['FECHA'].dt.month
        
        if 'VALOR US$ CIF' in df.columns and 'CANTIDAD' in df.columns:
            df['CIF_UNITARIO'] = df['VALOR US$ CIF'] / df['CANTIDAD']
        if 'FLETE' in df.columns and 'CANTIDAD' in df.columns:
            df['FLETE_UNITARIO'] = df['FLETE'] / df['CANTIDAD']
            
        return df
    except Exception as e:
        return None

# --- SIDEBAR ---
with st.sidebar:
    st.title("📊 EV Intelligence")
    
    # BUSCAMOS AUTOMÁTICAMENTE EL PARQUET
    archivo_local = "historial_lite.parquet"
    
    # Opción de subir archivo nuevo (Excel o Parquet)
    uploaded_file = st.file_uploader("Subir Archivo (Excel/Parquet)", type=["xlsx", "parquet"])
    
    df = None
    
    # Lógica de Prioridad
    if uploaded_file:
        df = cargar_datos(uploaded_file)
        if df is not None: st.success("✅ Datos Subidos Activos")
            
    elif os.path.exists(archivo_local):
        # Simulamos un objeto de archivo con atributo 'name' para que la función detecte parquet
        with open(archivo_local, 'rb') as f:
            # Truco para leer localmente usando la misma función
            df = pd.read_parquet(archivo_local)
            # Aplicamos limpieza rápida post-lectura si es necesario (el parquet ya guarda tipos de datos, es más seguro)
            # Replicamos limpieza básica por seguridad
            if 'FECHA' in df.columns:
                df['AÑO'] = df['FECHA'].dt.year
                df['MES_NUM'] = df['FECHA'].dt.month
            st.info("📂 Datos Precargados (Lite)")

    else:
        st.warning("⚠️ No se encontraron datos. Sube un archivo.")

    if df is not None:
        st.divider()
        modo = st.radio("Modo:", ["⚔️ Comparativo (VS)", "🔍 Deep Dive (Mensual)"], index=0)
        st.divider()

# --- LÓGICA PRINCIPAL (Igual que antes) ---
if df is not None:
    if modo == "⚔️ Comparativo (VS)":
        with st.sidebar:
            yrs = st.multiselect("Años", sorted(df['AÑO'].dropna().unique().astype(int), reverse=True), default=sorted(df['AÑO'].dropna().unique().astype(int), reverse=True)[:2])
            df_y = df[df['AÑO'].isin(yrs)]
            mks = st.multiselect("Marcas", sorted(df_y['MARCA'].unique()), default=[x for x in ['MG', 'GAC', 'AION'] if x in df_y['MARCA'].unique()])
            bdy = st.multiselect("Carrocería", sorted(df[df['MARCA'].isin(mks)]['CARROCERIA'].unique()), default=sorted(df[df['MARCA'].isin(mks)]['CARROCERIA'].unique()))
            
        df_f = df[(df['AÑO'].isin(yrs)) & (df['MARCA'].isin(mks)) & (df['CARROCERIA'].isin(bdy))].copy()
        
        if not df_f.empty:
            c_h1, c_h2 = st.columns([5, 1])
            with c_h1: st.title(f"⚔️ VS Mode: {', '.join(mks)}")
            with c_h2: st.info("🖨️ PDF: Ctrl+P")

            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader("Cuota de Mercado")
                st.plotly_chart(px.bar(df_f.groupby(['AÑO', 'MARCA'])['CANTIDAD'].sum().reset_index(), x='AÑO', y='CANTIDAD', color='MARCA', barmode='group', text_auto=True), use_container_width=True)
            with c2:
                st.subheader("Totales")
                st.dataframe(df_f.groupby('MARCA')['CANTIDAD'].sum().sort_values(ascending=False).reset_index(), use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("🕵️ Mercado Gris Agregado")
            mapa = {}
            for m in mks:
                d = df_f[df_f['MARCA'] == m]
                if not d.empty: mapa[m] = d.groupby('EMPRESA')['CANTIDAD'].sum().idxmax()
            df_f['TIPO'] = df_f.apply(lambda x: 'OFICIAL' if x['EMPRESA'] == mapa.get(x['MARCA']) else 'GRIS', axis=1)
            
            cg1, cg2 = st.columns(2)
            with cg1:
                st.plotly_chart(go.Figure(data=[go.Pie(labels=['Oficial', 'Gris'], values=[df_f[df_f['TIPO']=='OFICIAL']['CANTIDAD'].sum(), df_f[df_f['TIPO']=='GRIS']['CANTIDAD'].sum()], hole=.6, marker_colors=['#27AE60', '#95A5A6'])]), use_container_width=True)
            with cg2:
                st.write("**Top Importadores Gris:**")
                st.dataframe(df_f[df_f['TIPO']=='GRIS'].groupby('EMPRESA').agg(Autos=('CANTIDAD','sum'), Marcas=('MARCA', 'unique')).sort_values('Autos', ascending=False).head(5), use_container_width=True)

            st.divider()
            st.subheader("Evolución Precios CIF ($)")
            st.plotly_chart(px.line(df_f.groupby(['AÑO', 'MARCA'])['CIF_UNITARIO'].mean().reset_index(), x='AÑO', y='CIF_UNITARIO', color='MARCA', markers=True), use_container_width=True)

    elif modo == "🔍 Deep Dive (Mensual)":
        with st.sidebar:
            y = st.selectbox("Año", sorted(df['AÑO'].dropna().unique().astype(int), reverse=True))
            brands_y = sorted(df[df['AÑO']==y]['MARCA'].unique())
            m = st.selectbox("Marca", ["TODO EL MERCADO"] + brands_y)
        
        df_d = df[df['AÑO']==y].copy()
        if m != "TODO EL MERCADO": df_d = df_d[df_d['MARCA']==m]
        
        st.title(f"🔍 Análisis: {m} ({y})")
        k1, k2, k3 = st.columns(3)
        k1.metric("Unidades", f"{df_d['CANTIDAD'].sum():,.0f}")
        k2.metric("CIF Promedio", f"${df_d['CIF_UNITARIO'].mean():,.0f}")
        k3.metric("Inversión", f"${df_d['VALOR US$ CIF'].sum()/1e6:,.1f} M")
        
        tab1, tab2, tab3 = st.tabs(["Estacionalidad", "Logística", "Modelos"])
        
        with tab1:
            mensual = df_d.groupby('MES_NUM')['CANTIDAD'].sum().reset_index()
            mensual['Mes'] = mensual['MES_NUM'].apply(lambda x: calendar.month_abbr[int(x)])
            st.plotly_chart(px.line(mensual, x='Mes', y='CANTIDAD', markers=True), use_container_width=True)
        with tab2:
            st.subheader("Fletes")
            df_flt = df_d[(df_d['FLETE_UNITARIO'] > 50) & (df_d['FLETE_UNITARIO'] < 8000)]
            if not df_flt.empty:
                stats_f = df_flt.groupby('MES_NUM')['FLETE_UNITARIO'].agg(['min', 'max', 'mean']).reset_index()
                stats_f['Mes'] = stats_f['MES_NUM'].apply(lambda x: calendar.month_abbr[int(x)])
                fig_f = go.Figure()
                fig_f.add_trace(go.Scatter(x=stats_f['Mes'], y=stats_f['max'], mode='lines', showlegend=False))
                fig_f.add_trace(go.Scatter(x=stats_f['Mes'], y=stats_f['min'], mode='lines', fill='tonexty', fillcolor='rgba(46, 204, 113, 0.2)', name='Rango'))
                fig_f.add_trace(go.Scatter(x=stats_f['Mes'], y=stats_f['mean'], mode='lines+markers', line=dict(color='#27AE60', width=3), name='Promedio'))
                st.plotly_chart(fig_f, use_container_width=True)
            else: st.warning("Sin datos de flete.")
        with tab3:
            c1, c2 = st.columns(2)
            with c1: st.plotly_chart(px.bar(df_d.groupby('MODELO')['CANTIDAD'].sum().sort_values().tail(15), orientation='h', text_auto=True), use_container_width=True)
            with c2: 
                precios = df_d.groupby('MODELO').agg(Unidades=('CANTIDAD','sum'), Precio_Prom=('VALOR US$ CIF', 'sum'))
                precios['Precio_Prom'] = precios['Precio_Prom'] / precios['Unidades']
                st.dataframe(precios[precios['Unidades']>0].sort_values('Precio_Prom', ascending=False).style.format({'Precio_Prom': '${:,.0f}'}), use_container_width=True)

else:
    st.markdown("### ⚠️ Carga de Datos Requerida")
    st.warning("No se encontró 'historial_lite.parquet'. Asegúrate de subirlo o convertir tu Excel.")
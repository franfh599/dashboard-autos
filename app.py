import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import calendar
import os

# --- CONFIGURACIÓN DE PÁGINA ---
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

# --- CARGA DE DATOS CENTRALIZADA ---
@st.cache_data
def cargar_datos(source):
    """
    Carga datos desde un archivo subido (UploadedFile) o una ruta local (str).
    Aplica limpieza y cálculos siempre.
    """
    df = None
    try:
        # 1. LECTURA DEL ARCHIVO
        # Si es una ruta local (texto) y es parquet
        if isinstance(source, str) and source.endswith('.parquet'):
            df = pd.read_parquet(source)
        
        # Si es un archivo subido por el usuario (UploadedFile)
        else:
            try:
                df = pd.read_excel(source, sheet_name='2019-2025')
            except:
                df = pd.read_excel(source)

        if df is None: return None

        # 2. LIMPIEZA DE COLUMNAS
        df.columns = df.columns.str.strip().str.upper()
        
        # 3. LIMPIEZA DE TEXTOS
        cols_txt = ['MARCA', 'MODELO', 'EMPRESA', 'COMBUSTIBLE', 'MES', 'CARROCERIA', 'ESTILO']
        for c in cols_txt:
            if c in df.columns: 
                df[c] = df[c].astype(str).str.strip().str.upper()
                if c == 'MARCA':
                    df[c] = df[c].replace(['M.G.', 'MORRIS GARAGES', 'M. G.'], 'MG').replace(['BYD AUTO'], 'BYD')

        # Fallback Carrocería
        if 'CARROCERIA' not in df.columns:
            df['CARROCERIA'] = df['ESTILO'] if 'ESTILO' in df.columns else 'NO DEFINIDO'

        # 4. LIMPIEZA NUMÉRICA
        for c in ['CANTIDAD', 'VALOR US$ CIF', 'FLETE']:
            if c in df.columns:
                # Si ya es numérico (parquet) no hace falta replace, pero por seguridad en Excel:
                if df[c].dtype == 'object':
                    df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce').fillna(0)
                else:
                    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        
        # 5. FECHAS
        if 'FECHA' in df.columns:
            df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
            df['AÑO'] = df['FECHA'].dt.year
            df['MES_NUM'] = df['FECHA'].dt.month
        
        # 6. CÁLCULOS MATEMÁTICOS (AQUÍ ESTABA EL ERROR ANTES)
        # Calculamos CIF UNITARIO siempre, venga de donde venga el archivo
        if 'VALOR US$ CIF' in df.columns and 'CANTIDAD' in df.columns:
            df['CIF_UNITARIO'] = df['VALOR US$ CIF'] / df['CANTIDAD']
            # Evitar divisiones por cero o infinitos
            df['CIF_UNITARIO'] = df['CIF_UNITARIO'].fillna(0)

        if 'FLETE' in df.columns and 'CANTIDAD' in df.columns:
            df['FLETE_UNITARIO'] = df['FLETE'] / df['CANTIDAD']
            df['FLETE_UNITARIO'] = df['FLETE_UNITARIO'].fillna(0)
            
        return df
    except Exception as e:
        # En producción podrías imprimir e para debug: print(e)
        return None

# --- SIDEBAR ---
with st.sidebar:
    st.title("📊 EV Intelligence")
    
    archivo_local = "historial_lite.parquet"
    
    # 1. Opción Subir Archivo
    uploaded_file = st.file_uploader("Actualizar Data (Opcional)", type=["xlsx"])
    
    df = None
    
    # Lógica de Prioridad:
    if uploaded_file:
        df = cargar_datos(uploaded_file)
        if df is not None: st.success("✅ Datos Subidos")
            
    elif os.path.exists(archivo_local):
        # AQUÍ ESTÁ EL CAMBIO CLAVE: Usamos la misma función cargar_datos
        # pasándole la ruta del archivo parquet. Así se ejecutan los cálculos.
        df = cargar_datos(archivo_local)
        if df is not None: st.info("📂 Datos Precargados")

    else:
        st.warning("⚠️ No se encontraron datos.")

    if df is not None:
        st.divider()
        modo = st.radio("Modo:", ["⚔️ Comparativo (VS)", "🔍 Deep Dive (Mensual)"], index=0)
        st.divider()

# --- LÓGICA PRINCIPAL ---
if df is not None:
    
    # === MODO 1: COMPARATIVO ===
    if modo == "⚔️ Comparativo (VS)":
        with st.sidebar:
            yrs = st.multiselect("Años", sorted(df['AÑO'].dropna().unique().astype(int), reverse=True), default=sorted(df['AÑO'].dropna().unique().astype(int), reverse=True)[:2])
            df_y = df[df['AÑO'].isin(yrs)]
            mks = st.multiselect("Marcas", sorted(df_y['MARCA'].unique()), default=[x for x in ['MG', 'GAC', 'AION'] if x in df_y['MARCA'].unique()])
            body_opts = sorted(df[df['MARCA'].isin(mks)]['CARROCERIA'].unique())
            bdy = st.multiselect("Carrocería", body_opts, default=body_opts)
            
        df_f = df[(df['AÑO'].isin(yrs)) & (df['MARCA'].isin(mks)) & (df['CARROCERIA'].isin(bdy))].copy()
        
        if not df_f.empty:
            c_h1, c_h2 = st.columns([5, 1])
            with c_h1: st.title(f"⚔️ VS Mode: {', '.join(mks)}")
            with c_h2: st.info("🖨️ PDF: Ctrl+P")

            # Volumen
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader("Cuota de Mercado")
                st.plotly_chart(px.bar(df_f.groupby(['AÑO', 'MARCA'])['CANTIDAD'].sum().reset_index(), x='AÑO', y='CANTIDAD', color='MARCA', barmode='group', text_auto=True), use_container_width=True)
            with c2:
                st.subheader("Totales")
                st.dataframe(df_f.groupby('MARCA')['CANTIDAD'].sum().sort_values(ascending=False).reset_index(), use_container_width=True, hide_index=True)

            # Mercado Gris
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
                st.write("**Top Gris (Multimarca):**")
                st.dataframe(df_f[df_f['TIPO']=='GRIS'].groupby('EMPRESA').agg(Autos=('CANTIDAD','sum'), Marcas=('MARCA', 'unique')).sort_values('Autos', ascending=False).head(5), use_container_width=True)

            # Precios
            st.divider()
            st.subheader("Evolución Precios CIF ($)")
            # EL ERROR OCURRÍA AQUÍ PORQUE CIF_UNITARIO NO EXISTÍA
            # Ahora ya existe gracias a la función cargar_datos mejorada
            if 'CIF_UNITARIO' in df_f.columns:
                st.plotly_chart(px.line(df_f.groupby(['AÑO', 'MARCA'])['CIF_UNITARIO'].mean().reset_index(), x='AÑO', y='CIF_UNITARIO', color='MARCA', markers=True), use_container_width=True)
            else:
                st.error("No se pudo calcular el precio unitario. Verifica las columnas 'VALOR US$ CIF' y 'CANTIDAD'.")

    # === MODO 2: DEEP DIVE ===
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
    st.markdown("### ⚠️ Bienvenido")
    st.warning("No se encontraron datos precargados. Sube tu archivo a GitHub o usa el cargador manual.")

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import calendar
import os
import numpy as np
import streamlit.components.v1 as components  # Necesario para el botón PDF

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="EV Market Intelligence", 
    layout="wide", 
    page_icon="🚀",
    initial_sidebar_state="expanded"
)

# --- ESTILOS CSS (MÓVIL + PDF) ---
st.markdown("""
<style>
    .main {background-color: #f8f9fa;}
    h1, h2, h3 {font-family: 'Segoe UI', sans-serif; color: #2c3e50;}
    
    /* Botón de PDF destacado */
    .stButton button {
        background-color: #2c3e50;
        color: white;
        font-weight: bold;
        width: 100%;
    }
    .stButton button:hover {
        background-color: #34495e;
        color: white;
    }

    /* Ajustes Móvil */
    @media (max-width: 768px) { 
        .block-container {padding: 1rem 0.5rem !important;} 
        h1 {font-size: 1.5rem !important;} 
    }
    
    /* Lógica de Impresión PDF */
    @media print {
        [data-testid="stSidebar"], [data-testid="stHeader"], .stDeployButton, footer, .no-print {display: none !important;}
        body, .stApp {background-color: white !important; color: black !important;}
        .block-container {max-width: 100% !important; padding: 0 !important; margin: 0 !important;}
        body {zoom: 65%;}
    }
</style>
""", unsafe_allow_html=True)

# --- CARGA DE DATOS AUTOMÁTICA ---
@st.cache_data
def cargar_datos_automatico():
    archivo_objetivo = "historial_lite.parquet"
    if not os.path.exists(archivo_objetivo):
        return None, f"❌ ERROR: Falta '{archivo_objetivo}' en GitHub."
    
    try:
        df = pd.read_parquet(archivo_objetivo)
        
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
    st.title("🚀 EV Intelligence")
    
    df, mensaje = cargar_datos_automatico()
    
    if df is not None:
        st.success(f"✅ Online ({len(df):,.0f} regs)")
        st.divider()
        modo = st.radio("Modo:", ["⚔️ Comparativo (VS)", "🔍 Deep Dive (Detalle)"], index=0)
        st.divider()
        
        # BOTÓN PDF REAL (JAVASCRIPT)
        st.markdown("### 📥 Exportar")
        if st.button("🖨️ Generar PDF / Imprimir"):
            # Inyectamos Javascript para abrir el diálogo de impresión del navegador
            components.html("<script>window.print()</script>", height=0, width=0)
            
    else:
        st.error(mensaje)

# --- LÓGICA PRINCIPAL ---
if df is not None:
    
    # === MODO 1: COMPARATIVO (VS) ===
    if modo == "⚔️ Comparativo (VS)":
        with st.sidebar:
            st.subheader("Filtros Globales")
            
            # AÑOS: Marcado "Todos" por defecto (value=True)
            all_years = sorted(df['AÑO'].dropna().unique().astype(int), reverse=True)
            check_all_years = st.checkbox("Seleccionar Todos los Años", value=True)
            
            if check_all_years:
                yrs = all_years
            else:
                yrs = st.multiselect("Años", all_years, default=all_years[:1])
            
            df_y = df[df['AÑO'].isin(yrs)]
            
            # MARCAS: Marcado "Todas" por defecto (value=True)
            all_brands = sorted(df_y['MARCA'].unique())
            check_all_brands = st.checkbox("Seleccionar Todas las Marcas", value=True)
            
            if check_all_brands:
                mks = all_brands
            else:
                defaults = [x for x in ['MG', 'GAC'] if x in all_brands]
                mks = st.multiselect("Marcas", all_brands, default=defaults)
            
            body_opts = sorted(df[df['MARCA'].isin(mks)]['CARROCERIA'].unique())
            bdy = st.multiselect("Carrocería", body_opts, default=body_opts)
            
        df_f = df[(df['AÑO'].isin(yrs)) & (df['MARCA'].isin(mks)) & (df['CARROCERIA'].isin(bdy))].copy()
        
        if not df_f.empty:
            st.title(f"⚔️ Comparativo Total")
            
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
                vals = [df_f[df_f['TIPO']=='OFICIAL']['CANTIDAD'].sum(), df_f[df_f['TIPO']=='GRIS']['CANTIDAD'].sum()]
                st.plotly_chart(go.Figure(data=[go.Pie(labels=['Oficial', 'Gris'], values=vals, hole=.6, marker_colors=['#2ECC71', '#95A5A6'])]), use_container_width=True)
            with cg2:
                st.write("**Top Gris (Multimarca):**")
                st.dataframe(df_f[df_f['TIPO']=='GRIS'].groupby('EMPRESA').agg(Autos=('CANTIDAD','sum'), Marcas=('MARCA', 'unique')).sort_values('Autos', ascending=False).head(5), use_container_width=True)

            st.divider()
            st.subheader("📊 Distribución de Precios (Box Plot)")
            df_price = df_f[(df_f['CIF_UNITARIO'] > 1000) & (df_f['CIF_UNITARIO'] < 100000)]
            if not df_price.empty:
                st.plotly_chart(px.box(df_price, x='MARCA', y='CIF_UNITARIO', color='MARCA', points="outliers", title="Rango de Precios CIF"), use_container_width=True)

    # === MODO 2: DEEP DIVE ===
    elif modo == "🔍 Deep Dive (Detalle)":
        with st.sidebar:
            st.subheader("Filtros")
            y = st.selectbox("Año", sorted(df['AÑO'].dropna().unique().astype(int), reverse=True))
            df_y = df[df['AÑO']==y].copy()
            brands_y = sorted(df_y['MARCA'].unique())
            m = st.selectbox("Marca", ["TODO EL MERCADO"] + brands_y)
            combustibles_disponibles = sorted(df_y['COMBUSTIBLE'].unique())
            comb_sel = st.multiselect("⛽ Combustible", combustibles_disponibles, default=combustibles_disponibles)
        
        if m != "TODO EL MERCADO": df_y = df_y[df_y['MARCA']==m]
        df_d = df_y[df_y['COMBUSTIBLE'].isin(comb_sel)].copy()
        
        st.title(f"🔍 Análisis: {m} ({y})")
        
        if not df_d.empty:
            k1, k2, k3 = st.columns(3)
            k1.metric("Unidades", f"{df_d['CANTIDAD'].sum():,.0f}")
            k2.metric("CIF Promedio", f"${df_d['CIF_UNITARIO'].mean():,.0f}")
            k3.metric("Inversión", f"${df_d['VALOR US$ CIF'].sum()/1e6:,.1f} M")
            
            tab1, tab2, tab3, tab4 = st.tabs(["🔮 Tendencia", "⚖️ Pareto", "🚢 Logística", "📋 Modelos"])
            
            with tab1:
                mensual = df_d.groupby('MES_NUM')['CANTIDAD'].sum().reset_index()
                if len(mensual) > 1:
                    try:
                        # Try/Except para evitar crash si faltan librerías o datos
                        fig_t = px.scatter(mensual, x='MES_NUM', y='CANTIDAD', trendline="ols", trendline_color_override="red", title="Proyección")
                        fig_t.update_traces(mode='lines+markers')
                        fig_t.update_xaxes(tickmode='array', tickvals=list(range(1,13)), ticktext=[calendar.month_abbr[i] for i in range(1,13)])
                        st.plotly_chart(fig_t, use_container_width=True)
                    except:
                        st.warning("No se pudo calcular la tendencia (Falta statsmodels o datos insuficientes).")
                        st.plotly_chart(px.line(mensual, x='MES_NUM', y='CANTIDAD', markers=True), use_container_width=True)
                else: st.warning("Datos insuficientes para tendencia.")

            with tab2:
                pareto = df_d.groupby('MODELO')['CANTIDAD'].sum().sort_values(ascending=False).reset_index()
                pareto['Acum'] = pareto['CANTIDAD'].cumsum()
                pareto['%'] = (pareto['Acum']/pareto['CANTIDAD'].sum())*100
                fig_p = go.Figure([go.Bar(x=pareto['MODELO'], y=pareto['CANTIDAD'], name='Unds'), go.Scatter(x=pareto['MODELO'], y=pareto['%'], name='%', yaxis='y2', line=dict(color='red'))])
                fig_p.update_layout(yaxis2=dict(overlaying='y', side='right', range=[0, 110]))
                fig_p.add_hline(y=80, line_dash="dot", line_color="green", yref="y2")
                st.plotly_chart(fig_p, use_container_width=True)

            with tab3:
                df_flt = df_d[(df_d['FLETE_UNITARIO'] > 50) & (df_d['FLETE_UNITARIO'] < 8000)]
                if not df_flt.empty:
                    stats = df_flt.groupby('MES_NUM')['FLETE_UNITARIO'].agg(['min', 'max', 'mean']).reset_index()
                    stats['Mes'] = stats['MES_NUM'].apply(lambda x: calendar.month_abbr[int(x)])
                    fig_f = go.Figure()
                    fig_f.add_trace(go.Scatter(x=stats['Mes'], y=stats['max'], mode='lines', showlegend=False))
                    fig_f.add_trace(go.Scatter(x=stats['Mes'], y=stats['min'], mode='lines', fill='tonexty', fillcolor='rgba(46, 204, 113, 0.2)', name='Rango'))
                    fig_f.add_trace(go.Scatter(x=stats['Mes'], y=stats['mean'], mode='lines+markers', line=dict(color='#27AE60', width=3), name='Promedio'))
                    st.plotly_chart(fig_f, use_container_width=True)
                else: st.warning("Sin datos de flete.")

            with tab4:
                c1, c2 = st.columns(2)
                with c1: st.plotly_chart(px.bar(df_d.groupby('MODELO')['CANTIDAD'].sum().sort_values().tail(15), orientation='h', text_auto=True), use_container_width=True)
                with c2: 
                    precios = df_d.groupby('MODELO').agg(Unidades=('CANTIDAD','sum'), Precio_Prom=('VALOR US$ CIF', 'sum'))
                    precios['Precio_Prom'] = precios['Precio_Prom'] / precios['Unidades']
                    st.dataframe(precios[precios['Unidades']>0].sort_values('Precio_Prom', ascending=False).style.format({'Precio_Prom': '${:,.0f}'}), use_container_width=True)
        else:
            st.warning("No hay datos (revisa el filtro de Combustible).")

else:
    st.markdown("### ⚠️ Bienvenido")
    st.warning("Conectando con GitHub...")

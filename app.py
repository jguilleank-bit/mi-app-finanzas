import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import requests
from datetime import datetime

st.set_page_config(page_title="Portfolio Pro - Argentina", layout="wide")

# 1. UTILIDADES
def formato_moneda(valor, simbolo):
    try:
        val_f = f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{simbolo} {val_f}"
    except: return f"{simbolo} 0,00"

def limpiar_precio(valor):
    if pd.isna(valor) or valor == "": return 0.0
    s = str(valor).replace("$", "").strip()
    if "." in s and "," in s: s = s.replace(".", "")
    s = s.replace(",", ".")
    try: return float(s)
    except: return 0.0

@st.cache_data(ttl=600)
def get_dolar_mep():
    try:
        url = "https://criptoya.com/api/dolar"
        resp = requests.get(url, timeout=5).json()
        return float(resp['mep']['al30']['ci']['price'])
    except: return 1450.0

def load_data(url):
    try:
        sheet_id = url.split("/d/")[1].split("/")[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url)
        df.columns = df.columns.str.strip().str.lower()
        return df
    except: return None

# 2. CONFIGURACIÓN E INGESTIÓN
st.title("🚀 Mi Portfolio de Inversiones")
SHEET_URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"
mep_hoy = get_dolar_mep()

moneda_view = st.sidebar.selectbox("Visualizar en:", ["ARS (Pesos)", "USD (Dólares)"])
simb = "$" if moneda_view == "ARS (Pesos)" else "USD"
fact = 1.0 if moneda_view == "ARS (Pesos)" else (1.0 / mep_hoy)

df_raw = load_data(SHEET_URL)

if df_raw is not None and not df_raw.empty:
    try:
        df = df_raw.copy()
        df['cantidad'] = df['cantidad'].apply(limpiar_precio)
        df['precio_unitario'] = df['precio_unitario'].apply(limpiar_precio)
        df['mep_compra'] = df['cotizacion_mep_dia'].apply(limpiar_precio).replace(0.0, mep_hoy)

        # 3. PRECIOS VIVOS
        tickers = df['ticker'].dropna().unique().tolist()
        precios_vivos = {}
        with st.spinner('Actualizando cotizaciones...'):
            for t in tickers:
                try:
                    tkr = yf.Ticker(t)
                    hist = tkr.history(period="1d")
                    if not hist.empty:
                        px_last = float(hist['Close'].iloc[-1])
                        precios_vivos[t] = px_last if t.endswith(".BA") else px_last * mep_hoy
                    else: precios_vivos[t] = 0.0
                except: precios_vivos[t] = 0.0

        # 4. CÁLCULOS
        df['costo_ajustado_ars'] = (df['cantidad'] * df['precio_unitario'] / df['mep_compra']) * mep_hoy
        df['valor_hoy_ars'] = df.apply(lambda r: precios_vivos.get(r['ticker'], 0) * r['cantidad'], axis=1)
        df['ganancia_ars'] = df['valor_hoy_ars'] - df['costo_ajustado_ars']

        # 5. TABLA SUPERIOR (TOTALES)
        st.subheader("📊 Composición por Clase de Activo")
        df_tipo = df.groupby('tipo_activo').agg({'costo_ajustado_ars':'sum','valor_hoy_ars':'sum','ganancia_ars':'sum'}).reset_index()
        
        # Fila de Totales
        it, vt, gt = df_tipo['costo_ajustado_ars'].sum(), df_tipo['valor_hoy_ars'].sum(), df_tipo['ganancia_ars'].sum()
        tir_t = ((vt / it) - 1) * 100 if it > 0 else 0

        df_tipo_v = pd.DataFrame({
            'Tipo': df_tipo['tipo_activo'].str.upper(),
            'Inversión': (df_tipo['costo_ajustado_ars']*fact).apply(lambda x: formato_moneda(x, simb)),
            'Valor Actual': (df_tipo['valor_hoy_ars']*fact).apply(lambda x: formato_moneda(x, simb)),
            'Ganancia': (df_tipo['ganancia_ars']*fact).apply(lambda x: formato_moneda(x, simb)),
            'Rend.': ((df_tipo['valor_hoy_ars']/df_tipo['costo_ajustado_ars']-1)*100).map("{:.1f}%".format)
        })
        fila_total = pd.DataFrame({'Tipo':['TOTAL'],'Inversión':[formato_moneda(it*fact, simb)],'Valor Actual':[formato_moneda(vt*fact, simb)],'Ganancia':[formato_moneda(gt*fact, simb)],'Rend.':[f"{tir_t:.1f}%"]})
        st.dataframe(pd.concat([df_tipo_v, fila_total], ignore_index=True), hide_index=True, use_container_width=True)

        st.markdown("---")

        # 6. GRÁFICOS INTERMEDIOS (DISTRIBUCIÓN Y BROKER)
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🍩 Distribución por Tipo")
            st.plotly_chart(px.pie(df_tipo, values='valor_hoy_ars', names='tipo_activo', hole=.5), use_container_width=True)
        with col2:
            st.subheader("🏦 Capital por Broker")
            df_brk = df.groupby('broker')['valor_hoy_ars'].sum().reset_index()
            st.plotly_chart(px.bar(df_brk, x='broker', y=df_brk['valor_hoy_ars']*fact, color='broker', text_auto='.2s'), use_container_width=True)

        st.markdown("---")

        # 7. GRÁFICOS INFERIORES (LOS QUE SE HABÍAN PERDIDO - TICKERS)
        st.subheader("🔍 Detalle por Instrumento (Tickers)")
        df_tick = df.groupby('ticker').agg({'valor_hoy_ars':'sum', 'ganancia_ars':'sum'}).reset_index()
        
        c3, c4 = st.columns(2)
        with c3:
            st.plotly_chart(px.pie(df_tick, values='valor_hoy_ars', names='ticker', title="Peso de cada Ticker", hole=.4), use_container_width=True)
        with c4:
            st.plotly_chart(px.bar(df_tick.sort_values(by='ganancia_ars'), x='ticker', y=df_tick['ganancia_ars']*fact, 
                                   color='ganancia_ars', title=f"Ganancia Real por Activo ({simb})", color_continuous_scale='RdYlGn'), use_container_width=True)

    except Exception as e: st.error(f"Error en visualización: {e}")
else:
    st.info("Esperando conexión con la planilla de Google...")

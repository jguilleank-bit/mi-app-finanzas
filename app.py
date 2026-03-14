import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import requests
from datetime import datetime

st.set_page_config(page_title="Portfolio Pro - Argentina", layout="wide")

# 1. UTILIDADES DE FORMATEO Y LIMPIEZA
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

# 2. CONFIGURACIÓN INICIAL
st.title("🚀 Mi Portfolio de Inversiones")
SHEET_URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"
mep_hoy = get_dolar_mep()

st.sidebar.header("Configuración")
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

        # 3. PRECIOS EN VIVO
        tickers = df['ticker'].dropna().unique().tolist()
        precios_vivos_ars = {}
        with st.spinner('Sincronizando con el mercado...'):
            for t in tickers:
                try:
                    tkr = yf.Ticker(t)
                    hist = tkr.history(period="1d")
                    if not hist.empty:
                        last_px = float(hist['Close'].iloc[-1])
                        precios_vivos_ars[t] = last_px if t.endswith(".BA") else last_px * mep_hoy
                    else: precios_vivos_ars[t] = 0.0
                except: precios_vivos_ars[t] = 0.0

        # 4. CÁLCULOS
        df['costo_ajustado_ars'] = (df['cantidad'] * df['precio_unitario'] / df['mep_compra']) * mep_hoy
        df['valor_hoy_ars'] = df.apply(lambda r: precios_vivos_ars.get(r['ticker'], 0) * r['cantidad'], axis=1)
        df['ganancia_ars'] = df['valor_hoy_ars'] - df['costo_ajustado_ars']

        # 5. TABLA SUPERIOR: RESUMEN POR CLASE DE ACTIVO
        st.subheader("📊 Composición por Clase de Activo")
        df_tipo = df.groupby('tipo_activo').agg({
            'costo_ajustado_ars': 'sum',
            'valor_hoy_ars': 'sum',
            'ganancia_ars': 'sum'
        }).reset_index().sort_values(by='valor_hoy_ars', ascending=False)
        
        # Totales para la última fila
        inv_t = df_tipo['costo_ajustado_ars'].sum()
        val_t = df_tipo['valor_hoy_ars'].sum()
        gan_t = df_tipo['ganancia_ars'].sum()
        tir_t = ((val_t / inv_t) - 1) * 100 if inv_t > 0 else 0

        # Formateo de tabla
        df_tipo_v = pd.DataFrame({
            'Tipo': df_tipo['tipo_activo'].str.upper(),
            'Inversión': (df_tipo['costo_ajustado_ars']*fact).apply(lambda x: formato_moneda(x, simb)),
            'Valor Actual': (df_tipo['valor_hoy_ars']*fact).apply(lambda x: formato_moneda(x, simb)),
            'Ganancia': (df_tipo['ganancia_ars']*fact).apply(lambda x: formato_moneda(x, simb)),
            'Rend.': ((df_tipo['valor_hoy_ars']/df_tipo['costo_ajustado_ars']-1)*100).map("{:.1f}%".format)
        })
        
        fila_total = pd.DataFrame({
            'Tipo': ['TOTAL'],
            'Inversión': [formato_moneda(inv_t * fact, simb)],
            'Valor Actual': [formato_moneda(val_t * fact, simb)],
            'Ganancia': [formato_moneda(gan_t * fact, simb)],
            'Rend.': [f"{tir_t:.1f}%"]
        })
        
        st.dataframe(pd.concat([df_tipo_v, fila_total], ignore_index=True), hide_index=True, use_container_width=True)

        st.markdown("---")

        # 6. GRÁFICOS INFERIORES: TORTA (IZQ) Y BARRAS BROKER (DER)
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("🍩 Distribución por Tipo")
            fig_pie = px.pie(df_tipo, values='valor_hoy_ars', names='tipo_activo', hole=.5)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with c2:
            st.subheader("🏦 Capital por Broker")
            # Agrupamos por broker (asegúrate que la columna se llame 'broker' en tu Excel)
            df_broker = df.groupby('broker')['valor_hoy_ars'].sum().reset_index()
            fig_bar = px.bar(df_broker, x='broker', y=df_broker['valor_hoy_ars']*fact, 
                             text=(df_broker['valor_hoy_ars']*fact).apply(lambda x: formato_moneda(x, simb)),
                             color='broker', labels={'y': f'Total ({simb})'})
            fig_bar.update_traces(textposition='outside')
            st.plotly_chart(fig_bar, use_container_width=True)

    except Exception as e:
        st.error(f"Error en la ejecución: {e}")
else:
    st.info("Conecta tu Google Sheet para ver el análisis por Broker.")

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

        # 3. PRECIOS VIVOS
        tickers = df['ticker'].dropna().unique().tolist()
        precios_vivos = {}
        with st.spinner('Actualizando mercado...'):
            for t in tickers:
                try:
                    tkr = yf.Ticker(t)
                    hist = tkr.history(period="1d")
                    if not hist.empty:
                        px_last = float(hist['Close'].iloc[-1])
                        precios_vivos[t] = px_last if t.endswith(".BA") else px_last * mep_hoy
                    else: precios_vivos[t] = 0.0
                except: precios_vivos[t] = 0.0

        # 4. CÁLCULOS BASE
        df['costo_ajustado_ars'] = (df['cantidad'] * df['precio_unitario'] / df['mep_compra']) * mep_hoy
        df['valor_hoy_ars'] = df.apply(lambda r: precios_vivos.get(r['ticker'], 0) * r['cantidad'], axis=1)
        df['ganancia_ars'] = df['valor_hoy_ars'] - df['costo_ajustado_ars']

        # 5. MÉTRICAS PRINCIPALES (RESTAURADAS)
        inv_total_global = df['costo_ajustado_ars'].sum()
        val_total_global = df['valor_hoy_ars'].sum()
        gan_total_global = val_total_global - inv_total_global
        tir_global = ((val_total_global / inv_total_global) - 1) * 100 if inv_total_global > 0 else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("Valor Total Cartera", formato_moneda(val_total_global * fact, simb), delta=formato_moneda(gan_total_global * fact, simb))
        m2.metric("Inversión Ajustada", formato_moneda(inv_total_global * fact, simb))
        m3.metric("Rendimiento Total (TIR)", f"{tir_global:.2f}%")

        st.markdown("---")

        # 6. TABLA DE RESUMEN POR ACTIVO (CON FILA TOTAL)
        st.subheader("📊 Composición por Clase de Activo")
        df_tipo = df.groupby('tipo_activo').agg({'costo_ajustado_ars':'sum','valor_hoy_ars':'sum','ganancia_ars':'sum'}).reset_index().sort_values(by='valor_hoy_ars', ascending=False)
        
        df_tipo_v = pd.DataFrame({
            'Tipo': df_tipo['tipo_activo'].str.

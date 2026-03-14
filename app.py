import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import requests

st.set_page_config(page_title="Portfolio Pro", layout="wide")

# 1. FUNCIONES DE APOYO
def fmt_mon(v, s):
    try:
        vf = f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{s} {vf}"
    except: return f"{s} 0,00"

def clean_px(v):
    if pd.isna(v) or v == "": return 0.0
    s = str(v).replace("$", "").replace(".", "").replace(",", ".").strip()
    try: return float(s)
    except: return 0.0

@st.cache_data(ttl=600)
def get_mep():
    try:
        return float(requests.get("https://criptoya.com/api/dolar").json()['mep']['al30']['ci']['price'])
    except: return 1400.0

def load_data(url):
    try:
        sid = url.split("/d/")[1].split("/")[0]
        df = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv")
        df.columns = df.columns.str.strip().str.lower()
        return df
    except: return None

# 2. INICIO Y DATOS
st.title("🚀 Mi Portfolio de Inversiones")
URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"
mep = get_mep()

moneda = st.sidebar.selectbox("Moneda:", ["ARS (Pesos)", "USD (Dólares)"])
simb, fact = ("$", 1.0) if moneda == "ARS (Pesos)" else ("USD", 1.0/mep)

df_raw = load_data(URL)

if df_raw is not None and not df_raw.empty:
    df = df_raw.copy()
    for col in ['cantidad', 'precio_unitario', 'cotizacion_mep_dia']:
        df[col] = df[col].apply(clean_px)
    
    # Precios en Vivo
    tkrs = df['ticker'].unique()
    px_vivos = {}
    with st.spinner('Sincronizando...'):
        for t in tkrs:
            try:
                h = yf.Ticker(t).history(period="1d")
                p = float(h['Close'].iloc[-1])
                px_vivos[t] = p if t.endswith(".BA") else p * mep
            except: px_vivos[t] = 0.0

    # Cálculos
    df['costo_ars'] = (df['cantidad'] * df['precio_unitario'] / df['cotizacion_mep_dia'].replace(0, mep)) * mep
    df['val_hoy_ars'] = df.apply(lambda r: px_vivos.get(r['ticker'], 0) * r['cantidad'], axis=1)
    df['gan_ars'] = df['val_hoy_ars'] - df['costo_ars']

    # 3. MÉTRICAS TOP (Restauradas)
    inv_t, val_t = df['costo_ars'].sum(), df['val_hoy_ars'].sum()
    gan_t = val_t - inv_t
    tir_t = ((val_t / inv_t) - 1) * 100 if inv_t > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Valor Cartera", fmt_mon(val_t*fact, simb), f"{fmt_mon(gan_t*fact, simb)}")
    c2.metric("Inversión Ajustada", fmt_mon(inv_t*fact, simb))
    c3.metric("Rendimiento Total (TIR)", f"{tir_t:.2f}%")
    st.markdown("---")

    # 4. TABLA CON

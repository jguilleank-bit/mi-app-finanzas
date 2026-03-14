import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import requests

st.set_page_config(page_title="Terminal Inversiones Argentina", layout="wide")

def formato_ars(valor):
    try:
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "0,00"

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

def limpiar_numero(serie):
    s = serie.astype(str).str.replace(r'[^\d,.-]', '', regex=True)
    s = s.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    return pd.to_numeric(s, errors='coerce').fillna(0.0)

st.title("🚀 Mi Portfolio de Inversiones")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"
df_raw = load_data(SHEET_URL)
mep_hoy = get_dolar_mep()

st.sidebar.header("Configuración")
moneda_view = st.sidebar.selectbox("Visualizar en:", ["ARS (Pesos)", "USD (Dólares)"])

if df_raw is not None and not df_raw.empty:
    try:
        df = df_raw.copy()
        df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce')
        df['cantidad'] = limpiar_numero(df['cantidad'])
        df['precio_unitario'] = limpiar_numero(df['precio_unitario'])
        df['cotizacion_mep_dia'] = limpiar_numero(df.get('cotizacion_mep_dia', pd.Series([mep_hoy]*len(df))))
        df['cotizacion_mep_dia'] = df['cotizacion_mep_dia'].replace(0.0, mep_hoy)

        # Precios en vivo (Lógica BTC-USD corregida)
        tickers = df['ticker'].dropna().unique().tolist()
        precios_ars = {}
        for t in tickers:
            try:
                tkr = yf.Ticker(t)
                last

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import requests

st.set_page_config(page_title="Terminal Inversiones Argentina", layout="wide")

# Formateador visual estilo ARS
def formato_ars(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# API Dólar MEP en vivo
def get_dolar_mep():
    try:
        url = "https://criptoya.com/api/dolar"
        return float(requests.get(url).json()['mep']['al30']['ci']['price'])
    except: return 1250.0

# Lector de Google Sheets
def load_data(url):
    try:
        sheet_id = url.split("/d/")[1].split("/")[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url)
        df.columns = df.columns.str.strip().str.lower()
        return df
    except: return None

# Limpieza de números (Coma por Punto)
def limpiar_numero(serie):
    return serie.astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False).apply(pd.to_numeric, errors='coerce').fillna(0)

st.title("🚀 Mi Portfolio de Inversiones")

# --- REEMPLAZA CON TU LINK ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"

df_raw = load_data(SHEET_URL)
mep_hoy = get_dolar_mep()

st.sidebar.header("Configuración")
moneda_view = st.sidebar.selectbox("Visualizar en:", ["USD (Dólares)", "ARS (Pesos MEP)"])

if df_raw is not None and not df_raw.empty:
    try:
        df = df_raw.copy()
        df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce')
        
        # Limpieza de datos
        df['cantidad'] = limpiar_numero(df['cantidad'])
        df['precio_unitario'] = limpiar_numero(df['precio_unitario'])
        df['comision_total'] = limpiar_numero(df.get('comision_total', pd.Series([0]*len(df))))
        df['cotizacion_mep_dia'] = limpiar_numero(df.get('cotizacion_mep_dia', pd.Series([mep_hoy]*len(df))))
        df['cotizacion_mep_dia'] = df['cotizacion_mep_dia'].replace(0, mep_hoy)

        # Precios de Mercado
        tickers = df['ticker'].unique().tolist()
        with st.spinner('Actualizando precios...'):
            data_yf = yf.download(tickers, period="1d")['Close']
            precios_dict = {tickers[0]: float(data_yf.iloc[-1])} if len(tickers)==1 else data_yf.iloc[-1].to_dict()

        # LÓGICA FINANCIERA
        # 1. Costo Histórico Nominal (Lo que realmente pagaste en pesos/dólares en ese momento)
        df['costo_nominal_historico'] = (df['cantidad'] * df['precio_unitario']) + df['comision_total']

        # 2. Conversión a Dólar Base para comparación real
        def to_usd_base(row):
            if str(row['moneda_operacion']).upper() == 'ARS':
                return row['costo_nominal_historico'] / row['cotizacion_mep_dia']
            return row['costo_nominal_historico']
        
        df['costo_usd_base'] = df.apply(to_usd_base, axis=1)

        # 3. Valor de Mercado actual en Dólar Base
        def market_to_usd(row):
            p = precios_dict.get(row['ticker'], 0)
            if str(row['ticker']).upper().endswith

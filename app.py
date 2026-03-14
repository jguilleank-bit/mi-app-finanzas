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
@st.cache_data(ttl=600)
def get_dolar_mep():
    try:
        url = "https://criptoya.com/api/dolar"
        return float(requests.get(url).json()['mep']['al30']['ci']['price'])
    except:
        return 1420.0  # Valor de referencia si falla la API

# Lector de Google Sheets
def load_data(url):
    try:
        sheet_id = url.split("/d/")[1].split("/")[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url)
        df.columns = df.columns.str.strip().str.lower()
        return df
    except:
        return None

# Limpieza de números
def limpiar_numero(serie):
    return serie.astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False).apply(pd.to_numeric, errors='coerce').fillna(0)

st.title("🚀 Mi Portfolio de Inversiones")

# --- REEMPLAZA CON TU LINK ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"

df_raw = load_data(SHEET_URL)
mep_hoy = get_dolar_mep()

st.sidebar.header("Configuración")
moneda_view = st.sidebar.selectbox("Visualizar en:", ["ARS (Pesos)", "USD (Dólares)"])

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
        with st.spinner('Actualizando precios de mercado...'):
            precios_dict = {}
            for t in tickers:
                try:
                    ticker_data = yf.Ticker(t)
                    precios_dict[t] = ticker_data.history(period="1d")['Close'].iloc[-1]
                except:
                    precios_dict[t] = 0

        # LÓGICA DE COSTOS
        # 1. Costo Histórico: Lo que realmente pagaste (el valor de tu Excel)
        df['costo_historico_ars'] = (df['cantidad'] * df['precio_unitario']) + df['comision_total']
        
        # 2. Costo Ajustado: Dolarizamos al valor de compra y traemos al dólar de hoy
        df['costo_usd_compra'] = df['costo_historico_ars'] / df['cotizacion_mep_dia']
        df['costo_ajustado_hoy'] = df['costo_usd_compra'] * mep_hoy

        # 3. Valor Actual: Precio de mercado x Cantidad
        df['valor_actual_total'] = df['ticker'].map(precios_dict) * df['cantidad']
        
        # 4. Ganancia Real: Diferencia contra el costo ajustado (no contra el histórico)
        df['ganancia_real'] = df['valor_actual_total'] - df['costo_ajustado_hoy']

        # Selección de moneda para visualización
        factor = 1.0 if moneda_view == "ARS (Pesos)" else (1/mep_hoy)
        simbolo = "$" if moneda_view == "ARS (Pesos)" else "USD"

        # TABLA FINAL
        st.subheader("Detalle de Posiciones")
        df_display = pd.DataFrame({
            'Fecha': df['fecha'].dt.strftime('%d-%m-%Y'),
            'Ticker': df['ticker'],
            'Cant.': df['cantidad'],
            'Costo Histórico': df['costo_historico_ars'] * factor,
            'Costo Ajustado (Hoy)': df['costo_ajustado_hoy'] * factor,
            'Valor Actual': df['valor_actual_total'] * factor,
            'Ganancia Real': df['ganancia_real'] * factor
        })

        # Aplicar formato de moneda para lectura fácil
        for col in df_display.columns[3:]:
            df_display[col] = df_display[col].apply(lambda x: f"{simbolo} {formato_

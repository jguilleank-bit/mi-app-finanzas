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
        return 1400.0

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

# Limpieza robusta de números para formato latino (coma decimal)
def limpiar_numero(serie):
    serie = serie.astype(str).str.replace(r'[^\d,.-]', '', regex=True)
    serie = serie.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    return pd.to_numeric(serie, errors='coerce').fillna(0)

st.title("🚀 Mi Portfolio de Inversiones")

# Link de tu hoja ya integrado
SHEET_URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"

df_raw = load_data(SHEET_URL)
mep_hoy = get_dolar_mep()

st.sidebar.header("Configuración")
moneda_view = st.sidebar.selectbox("Visualizar en:", ["ARS (Pesos)", "USD (Dólares)"])

if df_raw is not None and not df_raw.empty:
    try:
        df = df_raw.copy()
        df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce')
        
        # Limpieza de columnas clave
        df['cantidad'] = limpiar_numero(df['cantidad'])
        df['precio_unitario'] = limpiar_numero(df['precio_unitario'])
        df['comision_total'] = limpiar_numero(df.get('comision_total', pd.Series([0]*len(df))))
        df['cotizacion_mep_dia'] = limpiar_numero(df.get('cotizacion_mep_dia', pd.Series([mep_hoy]*len(df))))
        df['cotizacion_mep_dia'] = df['cotizacion_mep_dia'].replace(0, mep_hoy)

        # Obtener precios de Yahoo Finance
        tickers = df['ticker'].unique().tolist()
        with st.spinner('Actualizando precios...'):
            precios_dict = {}
            for t in tickers:
                try:
                    ticker_data = yf.Ticker(t)
                    precios_dict[t] = ticker_data.history(period="1d")['Close'].iloc[-1]
                except:
                    precios_dict[t] = 0

        # CÁLCULOS
        df['costo_total_ars'] = (df['cantidad'] * df['precio_unitario']) + df['comision_total']
        df['costo_usd_compra'] = df['costo_total_ars'] / df['cotizacion_mep_dia']
        df['costo_ajustado_mep_hoy'] = df['costo_usd_compra'] * mep_hoy
        
        # Valor de mercado (si es .BA dividimos por MEP para estandarizar a USD y luego mostramos)
        def calcular_valor_actual(row):
            p = precios_dict.get(row['ticker'], 0)
            valor_ars = p * row['cantidad']
            return valor_ars # Yahoo Finance devuelve pesos para activos .BA

        df['valor_actual_ars'] = df.apply(calcular_valor_actual, axis=1)
        df['ganancia_real_ars'] = df['valor_actual_ars'] - df['costo_ajustado_mep_hoy']

        # Ajuste por moneda elegida
        f = 1.0 if moneda_view == "ARS (Pesos)" else (1/mep_hoy)
        s = "$" if moneda_view == "ARS (Pesos)" else "USD"

        # Métricas principales
        c1, c2, c3 = st.columns(3)
        total_inv = df['costo_ajustado_mep_hoy'].sum() * f
        total_mkt = df['valor_actual_ars'].sum() * f
        c1.metric("Inversión Ajustada", f"{s} {formato_ars(total_inv)}")
        c2.metric("Valor Cartera", f"{s} {formato_ars(total_mkt)}")
        c3.metric("Rendimiento Real", f"{((total_mkt/total_inv)-1)*100:.2f}%" if total_inv > 0 else "0%")

        # Tabla de Detalle
        st.subheader("Detalle de Posiciones")
        df_tab = pd.DataFrame({
            'Ticker': df['ticker'],
            'Cant.': df['cantidad'],
            'Costo Histórico': (df['costo_total_ars'] * f).apply(lambda x: f"{s} {formato_ars(x)}"),
            'Costo Ajustado': (df['costo_ajustado_mep_hoy'] * f).apply(lambda x: f"{s} {formato_ars(x)}"),
            'Valor Actual': (df['valor_actual_ars'] * f).apply(lambda x: f"{s} {formato_ars(x)}"),
            'Ganancia Real': (df['ganancia_real_ars'] * f).apply(lambda x: f"{s} {formato_ars(x)}")
        })
        st.dataframe(df_tab, use_container_width=True)

    except Exception as e:
        st.error(f"Error procesando datos: {e}")
else:
    st.warning("No se detectaron datos en la hoja de cálculo.")

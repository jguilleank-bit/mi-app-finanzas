import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px

st.set_page_config(page_title="Terminal Inversiones Pro", layout="wide")

def load_data(url):
    csv_url = url.replace('/edit?usp=sharing', '/export?format=csv')
    return pd.read_csv(csv_url)

st.title("🚀 Mi Portfolio de Inversiones")

# CONFIGURACIÓN: PEGA TU LINK AQUÍ
SHEET_URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"

try:
    df = load_data(SHEET_URL)
    df['fecha'] = pd.to_datetime(df['fecha'])
    
    # 1. Obtener Precios en Tiempo Real
    tickers = df['ticker'].unique().tolist()
    data = yf.download(tickers, period="1d")['Close']
    
    # Si solo hay un ticker, yfinance devuelve un float, lo corregimos
    if len(tickers) == 1:
        precios_dict = {tickers[0]: data.iloc[-1]}
    else:
        precios_dict = data.iloc[-1].to_dict()

    # 2. Cálculos de Valorización
    df['precio_actual'] = df['ticker'].map(precios_dict)
    df['valor_actual'] = df['cantidad'] * df['precio_actual']
    df['costo_total'] = (df['cantidad'] * df['precio_unitario']) + df['comision_total']
    df['rendimiento_usd'] = df['valor_actual'] - df['costo_total']
    df['rendimiento_perc'] = (df['rendimiento_usd'] / df['costo_total']) * 100

    # 3. DASHBOARD (UX de 1er Nivel)
    col1, col2, col3 = st.columns(3)
    total_invertido = df['costo_total'].sum()
    valor_total = df['valor_actual'].sum()
    ganancia_total = valor_total - total_invertido
    
    col1.metric("Inversión Total", f"USD {total_invertido:,.2f}")
    col2.metric("Valor Actual", f"USD {valor_total:,.2f}", f"{ganancia_total:,.2f}")
    col3.metric("Rendimiento Global", f"{(ganancia_total/total_invertido)*100:.2f}%")

    # Gráfico de Torta (Composición)
    fig_pie = px.pie(df, values='valor_actual', names='tipo_activo', title="Distribución por Activo")
    st.plotly_chart(fig_pie, use_container_width=True)

    # Tabla Detallada
    st.subheader("Detalle del Portafolio")
    st.dataframe(df[['fecha', 'ticker', 'tipo_activo', 'cantidad', 'precio_unitario', 'precio_actual', 'rendimiento_perc']], use_container_width=True)

except Exception as e:
    st.warning("Carga algunos datos en tu Google Sheet para empezar a ver la magia.")
    st.info("Asegúrate de que los Tickers sean correctos (ej: AAPL, BTC-USD).")

import streamlit as st
import pandas as pd
import yfinance as yf

# Configuración de la página (Experiencia de 1er nivel)
st.set_page_config(page_title="Mi Terminal Financiera", layout="wide")

# Función para leer Google Sheets de forma segura
def load_data(url):
    # Transformamos el link de edición en un link de descarga CSV
    csv_url = url.replace('/edit#gid=', '/export?format=csv&gid=')
    return pd.read_csv(csv_url)

# --- TÍTULO Y DATOS ---
st.title("📊 Mi Dashboard de Inversiones")

# Reemplaza esto con tu link copiado
SHEET_URL = "TU_LINK_DE_GOOGLE_SHEETS_AQUI"

try:
    df = load_data(SHEET_URL)
    
    # Cálculos Pro: Precio Actual
    unique_tickers = df['ticker'].unique()
    precios = yf.download(list(unique_tickers), period="1d")['Close'].iloc[-1]
    
    # Creamos la tabla de Portfolio
    st.subheader("Resumen de Activos")
    # Aquí iría la lógica de cálculo que definimos antes
    st.write(df) # Muestra tus datos actuales

except Exception as e:
    st.error(f"Error conectando datos: {e}")
    st.info("Asegúrate de que el link de Google Sheets sea público para lectura.")

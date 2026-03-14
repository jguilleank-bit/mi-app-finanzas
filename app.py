import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import requests

# 1. Configuración de página de 1er Nivel
st.set_page_config(page_title="Terminal Financiera Argentina", layout="wide")

# 2. Funciones de Datos
def get_dolar_mep():
    try:
        # API gratuita de CriptoYa para Dólar MEP (AL30)
        url = "https://criptoya.com/api/dolar"
        response = requests.get(url)
        data = response.json()
        return float(data['mep']['al30']['ci']['price'])
    except:
        return 1250.0  # Valor de respaldo por si falla la API

def load_data(url):
    try:
        sheet_id = url.split("/d/")[1].split("/")[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url)
        df.columns = df.columns.str.strip().str.lower()
        return df
    except:
        return None

# 3. Interfaz y Carga
st.title("🚀 Mi Portfolio de Inversiones")

# --- REEMPLAZA ESTE LINK CON EL TUYO ---
SHEET_URL = "TU_LINK_DE_GOOGLE_SHEETS_AQUI"

df_raw = load_data(SHEET_URL)
mep_hoy = get_dolar_mep()

# 4. Barra Lateral (Sidebar)
st.sidebar.header("Configuración")
moneda_view = st.sidebar.selectbox("Visualizar en:", ["USD (Dólares)", "ARS (Pesos MEP)"])

if df_raw is not None and not df_raw.empty:
    try:
        df = df_raw.copy()
        df['fecha'] = pd.to_datetime(df['fecha'])
        
        # Obtener precios de mercado
        tickers = df['ticker'].unique().tolist()
        with st.spinner('Consultando mercado internacional...'):
            data_yf = yf.download(tickers, period="1d")['Close']
            
            if len(tickers) == 1:
                precios_dict = {tickers[0]: float(data_yf.iloc[-1])}
            else:
                precios_dict = data_yf.iloc[-1].to_dict()

        # Cálculos de Negocio
        df['precio_actual_usd'] = df['ticker'].map(precios_dict).astype(float)
        df['cantidad'] = df['cantidad'].astype(float)
        df['precio_unitario_usd'] = df['precio_unitario'].astype(float) # Asumimos carga en USD para promediar
        
        # Valorización según moneda elegida
        if moneda_view == "ARS (Pesos MEP)":
            factor = mep_hoy
            label = "ARS"
            st.sidebar.info(f"Dólar MEP hoy: ${mep_hoy:,.2f}")
        else:
            factor = 1.0
            label = "USD"

        df['valor_actual'] = (df['cantidad'] * df['precio_actual_usd']) * factor
        df['costo_total'] = (df['cantidad'] * df['precio_unitario_usd']) * factor
        df['ganancia_abs'] = df['valor_actual'] - df['costo_total']

        # 5. Dashboard (Métricas)
        total_inv = df['costo_total'].sum()
        total_act = df['valor_actual'].sum()
        rend_porc = ((total_act / total_inv) - 1) * 100 if total_inv > 0 else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("Inversión Total", f"{label} {total_inv:,.2f}")
        m2.metric("Valor de Cartera", f"{label} {total_act:,.2f}", f"{total_act-total_inv:,.2f}")
        m3.metric("Rendimiento", f"{rend_porc:.2f}%")

        # 6. Gráficos
        c1, c2 = st.columns(2)
        with c1:
            fig_pie = px.pie(df, values='valor_actual', names='ticker', title="Distribución por Activo", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
        with c2:
            fig_bar = px.bar(df, x='ticker', y='ganancia_abs', title=f"Ganancia/Pérdida ({label})",
                             color='ganancia_abs', color_continuous_scale='RdYlGn')
            st.plotly_chart(fig_bar, use_container_width=True)

        # 7. Tabla Detallada
        st.subheader("Detalle de Posiciones")
        df_tab = df[['ticker', 'cantidad', 'precio_actual_usd', 'valor_actual', 'ganancia_abs']].round(2)
        st.dataframe(df_tab, use_container_width=True)

    except Exception as e:
        st.error(f"Hubo un problema procesando los activos: {e}")
else:
    st.info("💡 Esperando datos de Google Sheets. Verifica que el link sea correcto y tenga filas cargadas.")

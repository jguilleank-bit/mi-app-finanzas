import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import requests

# 1. Configuración de página
st.set_page_config(page_title="Terminal Inversiones Argentina", layout="wide")

# Función para formatear números a estilo ARS (1.000,00)
def formato_ars(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def get_dolar_mep():
    try:
        url = "https://criptoya.com/api/dolar"
        response = requests.get(url)
        data = response.json()
        return float(data['mep']['al30']['ci']['price'])
    except:
        return 1200.0

def load_data(url):
    try:
        sheet_id = url.split("/d/")[1].split("/")[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url)
        df.columns = df.columns.str.strip().str.lower()
        return df
    except:
        return None

# --- APP PRINCIPAL ---
st.title("🚀 Mi Portfolio de Inversiones")

# CONFIGURACIÓN: PEGA TU LINK AQUÍ
SHEET_URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"

df_raw = load_data(SHEET_URL)
mep_hoy = get_dolar_mep()

# Barra Lateral
st.sidebar.header("Configuración")
moneda_view = st.sidebar.selectbox("Visualizar en:", ["USD (Dólares)", "ARS (Pesos MEP)"])

if df_raw is not None and not df_raw.empty:
    try:
        df = df_raw.copy()
        df['fecha'] = pd.to_datetime(df['fecha'])
        
        # Obtener precios
        tickers = df['ticker'].unique().tolist()
        with st.spinner('Actualizando mercado...'):
            data_yf = yf.download(tickers, period="1d")['Close']
            precios_dict = {tickers[0]: float(data_yf.iloc[-1])} if len(tickers)==1 else data_yf.iloc[-1].to_dict()

        # Cálculos de Negocio
        df['precio_actual_usd'] = df['ticker'].map(precios_dict).astype(float)
        df['cantidad'] = df['cantidad'].astype(float)
        df['precio_unitario_usd'] = df['precio_unitario'].astype(float)
        
        # Selección de Moneda
        factor = mep_hoy if moneda_view == "ARS (Pesos MEP)" else 1.0
        simbolo = "ARS" if moneda_view == "ARS (Pesos MEP)" else "USD"

        df['valor_actual'] = (df['cantidad'] * df['precio_actual_usd']) * factor
        df['costo_total'] = (df['cantidad'] * df['precio_unitario_usd']) * factor
        df['ganancia_abs'] = df['valor_actual'] - df['costo_total']

        # 2. Métricas Principales con Formato Local
        total_inv = df['costo_total'].sum()
        total_act = df['valor_actual'].sum()
        rend_porc = ((total_act / total_inv) - 1) * 100 if total_inv > 0 else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("Inversión Total", f"{simbolo} {formato_ars(total_inv)}")
        m2.metric("Valor de Cartera", f"{simbolo} {formato_ars(total_act)}", f"{formato_ars(total_act-total_inv)}")
        m3.metric("Rendimiento Total", f"{rend_porc:.2f}%")

        # 3. Gráficos
        c1, c2 = st.columns(2)
        with c1:
            fig_pie = px.pie(df, values='valor_actual', names='ticker', title="Distribución de Activos", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
        with c2:
            fig_bar = px.bar(df, x='ticker', y='ganancia_abs', title=f"Ganancia/Pérdida ({simbolo})",
                             color='ganancia_abs', color_continuous_scale='RdYlGn')
            st.plotly_chart(fig_bar, use_container_width=True)

        # 4. Tabla Detallada con Formato Argentino
        st.subheader("Detalle de Posiciones")
        
        # Creamos una copia para mostrar con formato de texto
        df_display = df[['ticker', 'cantidad', 'precio_actual_usd', 'valor_actual', 'ganancia_abs']].copy()
        
        # Aplicamos el formato de miles y decimales a las columnas numéricas
        for col in ['precio_actual_usd', 'valor_actual', 'ganancia_abs']:
            df_display[col] = df_display[col].apply(formato_ars)
            
        st.dataframe(df_display, use_container_width=True)

        # 5. Sección de Inflación (Bonus Senior)
        st.divider()
        st.subheader("⚡ Análisis de Poder Adquisitivo (IPC)")
        inflacion_estimada = 211.4  # Ejemplo: Inflación anual último periodo
        st.write(f"Si la inflación fue del {inflacion_estimada}%, tu rendimiento real fue del **{rend_porc - inflacion_estimada:.2f}%**")

    except Exception as e:
        st.error(f"Error en el procesamiento: {e}")
else:
    st.info("💡 Sincronizando con Google Sheets...")

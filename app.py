import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px

st.set_page_config(page_title="Terminal Inversiones Pro", layout="wide")

# Función robusta de lectura
def load_data(url):
    try:
        # Extrae el ID de la hoja del link
        sheet_id = url.split("/d/")[1].split("/")[0]
        # Forzamos la lectura de la primera hoja (export?format=csv)
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url)
        # Limpieza de nombres de columnas para evitar errores de tipeo
        df.columns = df.columns.str.strip().str.lower()
        return df
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

st.title("🚀 Mi Portfolio de Inversiones")

# CONFIGURACIÓN: PEGA TU LINK AQUÍ
SHEET_URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"

df_raw = load_data(SHEET_URL)

if df_raw is not None and not df_raw.empty:
    try:
        # Procesamiento de datos
        df = df_raw.copy()
        df['fecha'] = pd.to_datetime(df['fecha'])
        
        # Obtener precios actuales
        tickers = df['ticker'].unique().tolist()
        with st.spinner('Actualizando precios de mercado...'):
            precios_data = yf.download(tickers, period="1d")['Close']
            
        if len(tickers) == 1:
            precios_dict = {tickers[0]: precios_data.iloc[-1]}
        else:
            precios_dict = precios_data.iloc[-1].to_dict()

        # Cálculos Financieros
        df['precio_actual'] = df['ticker'].map(precios_dict)
        df['valor_actual'] = df['cantidad'] * df['precio_actual']
        df['costo_total'] = (df['cantidad'] * df['precio_unitario']) + df['comision_total'].fillna(0)
        df['ganancia_abs'] = df['valor_actual'] - df['costo_total']
        
        # Dashboard Principal
        total_inv = df['costo_total'].sum()
        total_act = df['valor_actual'].sum()
        rend_total = ((total_act / total_inv) - 1) * 100

        m1, m2, m3 = st.columns(3)
        m1.metric("Inversión Total", f"USD {total_inv:,.2f}")
        m2.metric("Valor de Cartera", f"USD {total_act:,.2f}", f"{total_act-total_inv:,.2f}")
        m3.metric("Rendimiento", f"{rend_total:.2f}%")

        # Gráficos
        c1, c2 = st.columns(2)
        with c1:
            fig_pie = px.pie(df, values='valor_actual', names='tipo_activo', title="Distribución por Tipo")
            st.plotly_chart(fig_pie, use_container_width=True)
        with c2:
            fig_bar = px.bar(df, x='ticker', y='ganancia_abs', color='ganancia_abs', 
                             title="Ganancia/Pérdida por Activo", color_continuous_scale='RdYlGn')
            st.plotly_chart(fig_bar, use_container_width=True)

      st.subheader("Detalle de Posiciones")
        
        # Versión ultra-robusta de la tabla
        df_display = df[['fecha', 'ticker', 'tipo_activo', 'cantidad', 'precio_unitario', 'precio_actual', 'ganancia_abs']].copy()
        
        # Convertimos a string con formato para evitar el error de Series.format
        st.table(df_display.style.format({
            'precio_unitario': '{:.2f}', 
            'precio_actual': '{:.2f}', 
            'ganancia_abs': '{:.2f}'
        }))

    except Exception as e:
        st.error(f"Error procesando datos: {e}")
else:
    st.info("Esperando datos válidos de Google Sheets...")

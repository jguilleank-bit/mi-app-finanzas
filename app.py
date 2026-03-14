import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px

st.set_page_config(page_title="Terminal Inversiones Pro", layout="wide")

def load_data(url):
    try:
        sheet_id = url.split("/d/")[1].split("/")[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url)
        df.columns = df.columns.str.strip().str.lower()
        return df
    except:
        return None

st.title("🚀 Mi Portfolio de Inversiones")

# CONFIGURACIÓN: PEGA TU LINK AQUÍ
SHEET_URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"

df_raw = load_data(SHEET_URL)

if df_raw is not None and not df_raw.empty:
    try:
        df = df_raw.copy()
        df['fecha'] = pd.to_datetime(df['fecha'])
        
        # Obtener precios
        tickers = df['ticker'].unique().tolist()
        with st.spinner('Consultando mercado...'):
            precios_data = yf.download(tickers, period="1d")['Close']
            
        if len(tickers) == 1:
            precios_dict = {tickers[0]: precios_data.iloc[-1]}
        else:
            precios_dict = precios_data.iloc[-1].to_dict()

        # Cálculos
        df['precio_actual'] = df['ticker'].map(precios_dict)
        df['valor_actual'] = df['cantidad'] * df['precio_actual']
        df['costo_total'] = (df['cantidad'] * df['precio_unitario']) + df['comision_total'].fillna(0)
        df['ganancia_abs'] = df['valor_actual'] - df['costo_total']
        
        # Dashboard
        total_inv = df['costo_total'].sum()
        total_act = df['valor_actual'].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Inversión Total", f"USD {total_inv:,.2f}")
        m2.metric("Valor de Cartera", f"USD {total_act:,.2f}", f"{total_act-total_inv:,.2f}")
        if total_inv > 0:
            rend_total = ((total_act / total_inv) - 1) * 100
            m3.metric("Rendimiento", f"{rend_total:.2f}%")

        # Gráficos
        c1, c2 = st.columns(2)
        with c1:
            fig_pie = px.pie(df, values='valor_actual', names='tipo_activo', title="Distribución")
            st.plotly_chart(fig_pie, use_container_width=True)
        with c2:
            fig_bar = px.bar(df, x='ticker', y='ganancia_abs', title="Ganancia por Activo")
            st.plotly_chart(fig_bar, use_container_width=True)

        # TABLA FINAL ULTRA-ROBUSTA
        st.subheader("Detalle de Posiciones")
        
        # Mostramos la tabla sin formatos complejos para asegurar que cargue
        df_display = df[['ticker', 'cantidad', 'precio_unitario', 'precio_actual', 'ganancia_abs']].copy()
        
        # Redondeamos los números manualmente antes de mostrar
        df_display = df_display.round(2)
        
        # Usamos st.dataframe normal (sin .style) que es el más estable
        st.dataframe(df_display, use_container_width=True)

    except Exception as e:
        st.error(f"Error en cálculos: {e}")
        # En caso de error, mostramos los datos crudos para diagnosticar
        st.write("Datos procesados hasta el error:", df)
else:
    st.info("💡 Consejo: Revisa que tu Google Sheet tenga datos y el link sea correcto.")

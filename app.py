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
        
        # 1. Obtener Precios de forma ultra-robusta
        tickers = df['ticker'].unique().tolist()
        with st.spinner('Consultando mercado...'):
            # Descargamos los datos
            data = yf.download(tickers, period="1d")['Close']
            
            # Si es un solo ticker, data es una Serie. Si son varios, un DataFrame.
            # Convertimos siempre a un diccionario limpio de {Ticker: Precio}
            if len(tickers) == 1:
                precios_dict = {tickers[0]: float(data.iloc[-1])}
            else:
                precios_dict = data.iloc[-1].to_dict()

        # 2. Cálculos limpios
        df['precio_actual'] = df['ticker'].map(precios_dict).astype(float)
        df['cantidad'] = df['cantidad'].astype(float)
        df['precio_unitario'] = df['precio_unitario'].astype(float)
        df['comision_total'] = df['comision_total'].fillna(0).astype(float)
        
        df['valor_actual'] = df['cantidad'] * df['precio_actual']
        df['costo_total'] = (df['cantidad'] * df['precio_unitario']) + df['comision_total']
        df['ganancia_abs'] = df['valor_actual'] - df['costo_total']
        
        # 3. Dashboard visual
        total_inv = df['costo_total'].sum()
        total_act = df['valor_actual'].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Inversión Total", f"USD {total_inv:,.2f}")
        m2.metric("Valor de Cartera", f"USD {total_act:,.2f}", f"{total_act-total_inv:,.2f}")
        if total_inv > 0:
            rend_total = ((total_act / total_inv) - 1) * 100
            m3.metric("Rendimiento", f"{rend_total:.2f}%")

        # 4. Gráficos interactivos
        c1, c2 = st.columns(2)
        with c1:
            fig_pie = px.pie(df, values='valor_actual', names='tipo_activo', title="Distribución de Cartera")
            st.plotly_chart(fig_pie, use_container_width=True)
        with c2:
            fig_bar = px.bar(df, x='ticker', y='ganancia_abs', title="Ganancia/Pérdida por Activo",
                             color='ganancia_abs', color_continuous_scale='RdYlGn')
            st.plotly_chart(fig_bar, use_container_width=True)

        # 5. Tabla de detalle
        st.subheader("Detalle de Posiciones")
        df_display = df[['ticker', 'cantidad', 'precio_unitario', 'precio_actual', 'ganancia_abs']].round(2)
        st.dataframe(df_display, use_container_width=True)

    except Exception as e:
        st.error(f"Error en el procesamiento: {e}")
        st.write("Datos técnicos para soporte:", df[['ticker', 'precio_actual']].head())
else:
    st.info("💡 Consejo: Revisa que tu Google Sheet tenga datos y el link sea correcto.")

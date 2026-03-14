import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import requests

st.set_page_config(page_title="Terminal Inversiones Argentina", layout="wide")

def formato_ars(valor):
    try:
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "0,00"

@st.cache_data(ttl=600)
def get_dolar_mep():
    try:
        url = "https://criptoya.com/api/dolar"
        resp = requests.get(url, timeout=5).json()
        return float(resp['mep']['al30']['ci']['price'])
    except:
        return 1450.0

def load_data(url):
    try:
        sheet_id = url.split("/d/")[1].split("/")[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url)
        df.columns = df.columns.str.strip().str.lower()
        return df
    except:
        return None

def limpiar_numero(serie):
    s = serie.astype(str).str.replace(r'[^\d,.-]', '', regex=True)
    s = s.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    return pd.to_numeric(s, errors='coerce').fillna(0.0)

st.title("🚀 Mi Portfolio de Inversiones")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"
df_raw = load_data(SHEET_URL)
mep_hoy = get_dolar_mep()

st.sidebar.header("Configuración")
moneda_view = st.sidebar.selectbox("Visualizar en:", ["ARS (Pesos)", "USD (Dólares)"])

if df_raw is not None and not df_raw.empty:
    try:
        df = df_raw.copy()
        df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce')
        df['cantidad'] = limpiar_numero(df['cantidad'])
        df['precio_unitario'] = limpiar_numero(df['precio_unitario'])
        df['cotizacion_mep_dia'] = limpiar_numero(df.get('cotizacion_mep_dia', pd.Series([mep_hoy]*len(df))))
        df['cotizacion_mep_dia'] = df['cotizacion_mep_dia'].replace(0.0, mep_hoy)

        tickers = df['ticker'].dropna().unique().tolist()
        precios_en_ars = {}

        with st.spinner('Actualizando cotizaciones...'):
            for t in tickers:
                try:
                    tkr = yf.Ticker(t)
                    last_price = tkr.history(period="1d")['Close'].iloc[-1]
                    # Si no es Cedear (.BA), asumimos que el precio de Yahoo está en USD y pesificamos
                    precios_en_ars[t] = float(last_price) if ".BA" in t else float(last_price) * mep_hoy
                except:
                    precios_en_ars[t] = 0.0

        # CÁLCULOS UNIFICADOS
        df['costo_total_ars'] = (df['cantidad'] * df['precio_unitario'])
        df['costo_usd_compra'] = df['costo_total_ars'] / df['cotizacion_mep_dia']
        df['costo_ajustado_hoy'] = df['costo_usd_compra'] * mep_hoy
        df['valor_actual_ars'] = df.apply(lambda r: precios_en_ars.get(r['ticker'], 0) * r['cantidad'], axis=1)
        df['ganancia_real_ars'] = df['valor_actual_ars'] - df['costo_ajustado_hoy']

        # Ajuste de moneda para visualización
        f = 1.0 if moneda_view == "ARS (Pesos)" else (1.0 / mep_hoy)
        s = "$" if moneda_view == "ARS (Pesos)" else "USD"

        # --- MÉTRICAS CON TENDENCIA (DELTA) ---
        total_inv_ajustada = df['costo_ajustado_hoy'].sum() * f
        total_valor_actual = df['valor_actual_ars'].sum() * f
        ganancia_total = total_valor_actual - total_inv_ajustada
        rendimiento_pct = ((total_valor_actual / total_inv_ajustada) - 1) * 100 if total_inv_ajustada > 0 else 0.0

        c1, c2, c3 = st.columns(3)
        c1.metric("Inversión Ajustada", f"{s} {formato_ars(total_inv_ajustada)}")
        
        # Aquí vuelve el valor en verde indicando la ganancia absoluta
        c2.metric("Valor Actual Cartera", 
                  f"{s} {formato_ars(total_valor_actual)}", 
                  delta=f"{s} {formato_ars(ganancia_total)}")
        
        c3.metric("Rendimiento Total", f"{rendimiento_pct:.2f}%")

        st.markdown("---")

        # Gráficos
        df_g = df.groupby('ticker').agg({'valor_actual_ars':'sum', 'ganancia_real_ars':'sum'}).reset_index()
        g1, g2 = st.columns(2)
        with g1:
            fig_pie = px.pie(df_g, values='valor_actual_ars', names='ticker', title="Distribución de Cartera", hole=.4)
            st.plotly_chart(fig_pie, use_container_width=True)
        with g2:
            fig_bar = px.bar(df_g, x='ticker', y=df_g['ganancia_real_ars']*f, color='ganancia_real_ars', 
                             title=f"Ganancia/Pérdida por Activo ({s})", color_continuous_scale='RdYlGn')
            st.plotly_chart(fig_bar, use_container_width=True)

        st.subheader("Detalle de Posiciones")
        df_p = pd.DataFrame({
            'Ticker': df['ticker'],
            'Cant.': df['cantidad'],
            'Costo Compra': (df['costo_total_ars'] * f).apply(lambda x: f"{s} {formato_ars(x)}"),
            'Valor Hoy': (df['valor_actual_ars'] * f).apply(lambda x: f"{s} {formato_ars(x)}"),
            'Ganancia Real': (df['ganancia_real_ars'] * f).apply(lambda x: f"{s} {formato_ars(x)}")
        })
        st.dataframe(df_p, use_container_width=True)

    except Exception as e:
        st.error(f"Error en los cálculos: {e}")
else:
    st.warning("No se detectaron datos en la hoja.")

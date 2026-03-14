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
    except Exception:
        return 1450.0 # Valor de respaldo

def load_data(url):
    try:
        sheet_id = url.split("/d/")[1].split("/")[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url)
        df.columns = df.columns.str.strip().str.lower()
        return df
    except Exception:
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

        with st.spinner('Sincronizando precios (BTC y Cedears)...'):
            for t in tickers:
                try:
                    # Si pides BTC-USD o cualquier cripto, lo pasamos a ARS usando el MEP
                    tkr = yf.Ticker(t)
                    last_price = tkr.history(period="1d")['Close'].iloc[-1]
                    
                    if ".BA" in t:
                        precios_en_ars[t] = float(last_price)
                    else:
                        # Es un activo en USD (como BTC-USD), lo pesificamos al MEP de hoy
                        precios_en_ars[t] = float(last_price) * mep_hoy
                except:
                    precios_en_ars[t] = 0.0

        # Cálculos unificados en ARS
        df['costo_total_ars'] = (df['cantidad'] * df['precio_unitario'])
        df['costo_usd_compra'] = df['costo_total_ars'] / df['cotizacion_mep_dia']
        df['costo_ajustado_hoy'] = df['costo_usd_compra'] * mep_hoy
        df['valor_actual_ars'] = df.apply(lambda r: precios_en_ars.get(r['ticker'], 0) * r['cantidad'], axis=1)
        df['ganancia_real_ars'] = df['valor_actual_ars'] - df['costo_ajustado_hoy']

        # Ajuste de visualización
        f = 1.0 if moneda_view == "ARS (Pesos)" else (1.0 / mep_hoy)
        s = "$" if moneda_view == "ARS (Pesos)" else "USD"

        # Métricas
        t_inv = df['costo_ajustado_hoy'].sum() * f
        t_mkt = df['valor_actual_ars'].sum() * f
        c1, c2, c3 = st.columns(3)
        c1.metric("Inversión Ajustada", f"{s} {formato_ars(t_inv)}")
        c2.metric("Valor Actual", f"{s} {formato_ars(t_mkt)}")
        c3.metric("Rendimiento", f"{(((t_mkt/t_inv)-1)*100):.2f}%" if t_inv > 0 else "0%")

        # Gráficos consolidados
        df_g = df.groupby('ticker').agg({'valor_actual_ars':'sum', 'ganancia_real_ars':'sum'}).reset_index()
        g1, g2 = st.columns(2)
        with g1:
            st.plotly_chart(px.pie(df_g, values='valor_actual_ars', names='ticker', title="Reparto de Cartera", hole=.4), use_container_width=True)
        with g2:
            st.plotly_chart(px.bar(df_g, x='ticker', y=df_g['ganancia_real_ars']*f, color='ganancia_real_ars', title=f"Ganancia Real ({s})", color_continuous_scale='RdYlGn'), use_container_width=True)

        st.subheader("Listado de Operaciones")
        df_p = pd.DataFrame({
            'Ticker': df['ticker'],
            'Cant.': df['cantidad'],
            'Costo Compra': (df['costo_total_ars'] * f).apply(lambda x: f"{s} {formato_ars(x)}"),
            'Valor Hoy': (df['valor_actual_ars'] * f).apply(lambda x: f"{s} {formato_ars(x)}"),
            'Ganancia Real': (df['ganancia_real_ars'] * f).apply(lambda x: f"{s} {formato_ars(x)}")
        })
        st.dataframe(df_p, use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")

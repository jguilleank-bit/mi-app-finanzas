import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import requests
from datetime import datetime

st.set_page_config(page_title="Terminal Inversiones Argentina", layout="wide")

def formato_ars(valor):
    try:
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except: return "0,00"

@st.cache_data(ttl=600)
def get_dolar_mep():
    try:
        url = "https://criptoya.com/api/dolar"
        resp = requests.get(url, timeout=5).json()
        return float(resp['mep']['al30']['ci']['price'])
    except: return 1450.0

def load_data(url):
    try:
        sheet_id = url.split("/d/")[1].split("/")[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url)
        df.columns = df.columns.str.strip().str.lower()
        return df
    except: return None

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

        # Precios en vivo
        tickers = df['ticker'].dropna().unique().tolist()
        precios_ars = {}
        for t in tickers:
            try:
                tkr = yf.Ticker(t)
                last = tkr.history(period="1d")['Close'].iloc[-1]
                precios_ars[t] = float(last) if ".BA" in t else float(last) * mep_hoy
            except: precios_ars[t] = 0.0

        # Cálculos de rentabilidad temporal
        hoy = pd.Timestamp.now()
        df['dias_antiguedad'] = (hoy - df['fecha']).dt.days
        df['costo_total_ars'] = df['cantidad'] * df['precio_unitario']
        df['costo_ajustado_hoy'] = (df['costo_total_ars'] / df['cotizacion_mep_dia']) * mep_hoy
        df['valor_actual_ars'] = df.apply(lambda r: precios_ars.get(r['ticker'], 0) * r['cantidad'], axis=1)
        df['ganancia_ars'] = df['valor_actual_ars'] - df['costo_ajustado_hoy']

        # Conversión de vista
        f = 1.0 if moneda_view == "ARS (Pesos)" else (1.0 / mep_hoy)
        s = "$" if moneda_view == "ARS (Pesos)" else "USD"

        # Métricas principales
        inv_total = df['costo_ajustado_hoy'].sum() * f
        val_total = df['valor_actual_ars'].sum() * f
        gan_total = val_total - inv_total
        rend_total_pct = ((val_total / inv_total) - 1) * 100 if inv_total > 0 else 0
        
        # Rendimiento Anualizado Estimado (TIR simplificada)
        antiguedad_media = df['dias_antiguedad'].mean()
        años = antiguedad_media / 365
        rend_anualizado = ((1 + rend_total_pct/100)**(1/años) - 1) * 100 if años > 0.1 else rend_total_pct

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Inversión Ajustada", f"{s} {formato_ars(inv_total)}")
        m2.metric("Valor Cartera", f"{s} {formato_ars(val_total)}", delta=f"{s} {formato_ars(gan_total)}")
        m3.metric("Rendimiento Total", f"{rend_total_pct:.2f}%")
        m4.metric("Rendimiento Anualizado", f"{rend_anualizado:.2f}%", help="Equivalente anual de tu ganancia")

        st.info(f"📅 **Contexto temporal:** Tu cartera tiene una antigüedad promedio de **{antiguedad_media:.0f} días** (~{años:.1f} años).")

        # Gráficos y Tabla
        g1, g2 = st.columns(2)
        df_g = df.groupby('ticker').agg({'valor_actual_ars':'sum', 'ganancia_ars':'sum'}).reset_index()
        with g1: st.plotly_chart(px.pie(df_g, values='valor_actual_ars', names='ticker', title="Distribución", hole=.4), use_container_width=True)
        with g2: st.plotly_chart(px.bar(df_g, x='ticker', y=df_g['ganancia_ars']*f, color='ganancia_ars', title=f"Ganancia por Activo ({s})", color_continuous_scale='RdYlGn'), use_container_width=True)

        st.subheader("Análisis por Operación")
        df_tab = pd.DataFrame({
            'Fecha': df['fecha'].dt.strftime('%d/%m/%y'),
            'Ticker': df['ticker'],
            'Días': df['dias_antiguedad'],
            'Rend. Simple': ((df['valor_actual_ars']/df['costo_ajustado_hoy'] - 1)*100).map("{:.1f}%".format),
            'Valor Hoy': (df['valor_actual_ars']*f).apply(lambda x: f"{s} {formato_ars(x)}")
        })
        st.dataframe(df_tab, use_container_width=True)

    except Exception as e: st.error(f"Error: {e}")

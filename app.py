import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import requests
from datetime import datetime

st.set_page_config(page_title="Portfolio Pro - Argentina", layout="wide")

# 1. UTILIDADES DE FORMATEO Y LIMPIEZA
def formato_moneda(valor, simbolo):
    try:
        val_f = f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{simbolo} {val_f}"
    except: return f"{simbolo} 0,00"

def limpiar_precio(valor):
    """Convierte '9.484,59' o '9484,59' en float 9484.59"""
    if pd.isna(valor) or valor == "": return 0.0
    s = str(valor).replace("$", "").strip()
    # Si hay punto y coma, el punto suele ser de miles (lo sacamos)
    if "." in s and "," in s:
        s = s.replace(".", "")
    # Cambiamos la coma decimal por punto
    s = s.replace(",", ".")
    try: return float(s)
    except: return 0.0

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

# 2. CONFIGURACIÓN INICIAL
st.title("🚀 Mi Portfolio de Inversiones")
SHEET_URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"
mep_hoy = get_dolar_mep()

st.sidebar.header("Configuración")
moneda_view = st.sidebar.selectbox("Visualizar en:", ["ARS (Pesos)", "USD (Dólares)"])
simb = "$" if moneda_view == "ARS (Pesos)" else "USD"
fact = 1.0 if moneda_view == "ARS (Pesos)" else (1.0 / mep_hoy)

df_raw = load_data(SHEET_URL)

if df_raw is not None and not df_raw.empty:
    try:
        df = df_raw.copy()
        # Limpieza profunda de datos
        df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce')
        df['cantidad'] = df['cantidad'].apply(limpiar_precio)
        df['precio_unitario'] = df['precio_unitario'].apply(limpiar_precio)
        df['mep_compra'] = df['cotizacion_mep_dia'].apply(limpiar_precio).replace(0.0, mep_hoy)

        # 3. OBTENCIÓN DE PRECIOS EN VIVO
        tickers = df['ticker'].dropna().unique().tolist()
        precios_vivos_ars = {}
        
        with st.spinner('Sincronizando con el mercado...'):
            for t in tickers:
                try:
                    tkr = yf.Ticker(t)
                    # Tomamos el último cierre
                    px_hist = tkr.history(period="1d")
                    last_px = float(px_hist['Close'].iloc[-1])
                    # Si no es CEDEAR (.BA), pesificamos el precio de USD a ARS
                    precios_vivos_ars[t] = last_px if t.endswith(".BA") else last_px * mep_hoy
                except: precios_vivos_ars[t] = 0.0

        # 4. CÁLCULOS DE RENTABILIDAD
        df['costo_total_ars'] = df['cantidad'] * df['precio_unitario']
        # Costo ajustado: lo que pusiste hoy medido en MEP actual
        df['costo_ajustado_ars'] = (df['costo_total_ars'] / df['mep_compra']) * mep_hoy
        df['valor_hoy_ars'] = df.apply(lambda r: precios_vivos_ars.get(r['ticker'], 0) * r['cantidad'], axis=1)
        df['ganancia_ars'] = df['valor_hoy_ars'] - df['costo_ajustado_ars']
        
        # Rendimiento temporal
        dias_pje = (pd.Timestamp.now() - df['fecha']).dt.days.mean()
        años = max(dias_pje / 365, 0.1)

        # 5. MÉTRICAS MACRO
        inv_total = df['costo_ajustado_ars'].sum() * fact
        val_total = df['valor_hoy_ars'].sum() * fact
        gan_total = val_total - inv_total
        rend_total = ((val_total / inv_total) - 1) * 100 if inv_total > 0 else 0
        rend_anual = ((1 + rend_total/100)**(1/años) - 1) * 100

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Inversión Ajustada", formato_moneda(inv_total, simb))
        m2.metric("Valor Cartera", formato_moneda(val_total, simb), delta=formato_moneda(gan_total, simb))
        m3.metric("Rendimiento Total", f"{rend_total:.2f}%")
        m4.metric("Rend. Anualizado", f"{rend_anual:.2f}%")

        st.markdown("---")

        # 6. RESUMEN POR TIPO DE ACTIVO (ORDENADO + TORTA)
        st.subheader("📊 Composición por Clase de Activo")
        df_tipo = df.groupby('tipo_activo').agg({
            'costo_ajustado_ars': 'sum',
            'valor_hoy_ars': 'sum',
            'ganancia_ars': 'sum'
        }).reset_index().sort_values(by='valor_hoy_ars', ascending=False)
        
        c_tab, c_pie = st.columns([0.6, 0.4])
        with c_tab:
            df_tipo_v = pd.DataFrame({
                'Tipo': df_tipo['tipo_activo'].str.upper(),
                'Inversión': (df_tipo['costo_ajustado_ars']*fact).apply(lambda x: formato_moneda(x, simb)),
                'Valor Actual': (df_tipo['valor_hoy_ars']*fact).apply(lambda x: formato_moneda(x, simb)),
                'Ganancia': (df_tipo['ganancia_ars']*fact).apply(lambda x: formato_moneda(x, simb)),
                'Rend.': ((df_tipo['valor_hoy_ars']/df_tipo['costo_ajustado_ars']-1)*100).map("{:.1f}%".format)
            })
            st.dataframe(df_tipo_v, hide_index=True, use_container_width=True)
        
        with c_pie:
            st.plotly_chart(px.pie(df_tipo, values='valor_hoy_ars', names='tipo_activo', hole=.5), use_container_width=True)

        st.markdown("---")

        # 7. DESGLOSE POR TICKER
        st.subheader("🔍 Detalle por Instrumento")
        df_tick = df.groupby('ticker').agg({'valor_hoy_ars':'sum', 'ganancia_ars':'sum'}).reset_index()
        g1, g2 = st.columns(2)
        with g1: st.plotly_chart(px.pie(df_tick, values='valor_hoy_ars', names='ticker', title="Peso de Tickers", hole=.4), use_container_width=True)
        with g2: st.plotly_chart(px.bar(df_tick.sort_values(by='ganancia_ars'), x='ticker', y=df_tick['ganancia_ars']*fact, color='ganancia_ars', title=f"Ganancia Absoluta ({simb})", color_continuous_scale='RdYlGn'), use_container_width=True)

    except Exception as e:
        st.error(f"Hubo un problema con los datos: {e}")
else:
    st.info("Conecta tu Google Sheet para empezar a ver los datos.")

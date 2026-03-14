import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import requests

st.set_page_config(page_title="Terminal Inversiones Argentina", layout="wide")

# Formateador visual
def formato_ars(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# API Dólar MEP
def get_dolar_mep():
    try:
        url = "https://criptoya.com/api/dolar"
        return float(requests.get(url).json()['mep']['al30']['ci']['price'])
    except: return 1200.0

# Lector de Google Sheets
def load_data(url):
    try:
        sheet_id = url.split("/d/")[1].split("/")[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url)
        df.columns = df.columns.str.strip().str.lower()
        return df
    except: return None

# Función de Limpieza de formato Argentino (Coma por Punto)
def limpiar_numero(serie):
    # Transforma '9.484,59' -> '9484.59' -> float
    return serie.astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False).apply(pd.to_numeric, errors='coerce').fillna(0)

st.title("🚀 Mi Portfolio de Inversiones")

# CONFIGURACIÓN: PEGA TU LINK AQUÍ
SHEET_URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"

df_raw = load_data(SHEET_URL)
mep_hoy = get_dolar_mep()

st.sidebar.header("Configuración")
moneda_view = st.sidebar.selectbox("Visualizar en:", ["USD (Dólares)", "ARS (Pesos MEP)"])

if df_raw is not None and not df_raw.empty:
    try:
        df = df_raw.copy()
        df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce')
        
        # 1. Limpiamos las columnas numéricas de comas
        df['cantidad'] = limpiar_numero(df['cantidad'])
        df['precio_unitario'] = limpiar_numero(df['precio_unitario'])
        
        if 'cotizacion_mep_dia' in df.columns:
            df['cotizacion_mep_dia'] = limpiar_numero(df['cotizacion_mep_dia'])
            # Si el MEP del día está en cero o vacío, usamos el MEP de hoy para evitar errores
            df['cotizacion_mep_dia'] = df['cotizacion_mep_dia'].replace(0, mep_hoy)
        else:
            df['cotizacion_mep_dia'] = mep_hoy

        # 2. Buscamos Precios en Yahoo Finance
        tickers = df['ticker'].unique().tolist()
        with st.spinner('Actualizando mercado...'):
            data_yf = yf.download(tickers, period="1d")['Close']
            precios_dict = {tickers[0]: float(data_yf.iloc[-1])} if len(tickers)==1 else data_yf.iloc[-1].to_dict()

        # 3. LÓGICA DE COSTOS (Convirtiendo todo a Dólar Base)
        def calc_compra_usd(row):
            # Si compró en pesos, el costo real en USD es el precio dividido el MEP de ese día
            if str(row.get('moneda_operacion', '')).upper() == 'ARS':
                return row['precio_unitario'] / row['cotizacion_mep_dia']
            return row['precio_unitario'] # Si ya está en USD, lo deja igual
            
        df['precio_compra_usd_base'] = df.apply(calc_compra_usd, axis=1)

        def calc_mercado_usd(ticker, precio):
            # Si el ticker es argentino (.BA), Yahoo lo da en Pesos. Lo pasamos a USD.
            if str(ticker).upper().endswith('.BA'):
                return precio / mep_hoy
            return precio
            
        df['precio_mercado_usd_base'] = df.apply(lambda x: calc_mercado_usd(x['ticker'], precios_dict.get(x['ticker'], 0)), axis=1)

        # 4. Cálculos Totales en Base USD
        df['costo_total_base'] = df['cantidad'] * df['precio_compra_usd_base']
        df['valor_actual_base'] = df['cantidad'] * df['precio_mercado_usd_base']

        # 5. Aplicar Filtro de Moneda Visual
        factor = mep_hoy if moneda_view == "ARS (Pesos MEP)" else 1.0
        simbolo = "ARS" if moneda_view == "ARS (Pesos MEP)" else "USD"

        df['Costo Final'] = df['costo_total_base'] * factor
        df['Valor Actual'] = df['valor_actual_base'] * factor
        df['Ganancia'] = df['Valor Actual'] - df['Costo Final']

        # MÉTRICAS PRINCIPALES
        total_inv = df['Costo Final'].sum()
        total_act = df['Valor Actual'].sum()
        rend_porc = ((total_act / total_inv) - 1) * 100 if total_inv > 0 else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("Inversión Total", f"{simbolo} {formato_ars(total_inv)}")
        m2.metric("Valor de Cartera", f"{simbolo} {formato_ars(total_act)}", f"{formato_ars(total_act-total_inv)}")
        m3.metric("Rendimiento", f"{rend_porc:.2f}%")

        # GRÁFICOS
        c1, c2 = st.columns(2)
        with c1:
            fig_pie = px.pie(df, values='Valor Actual', names='ticker', title="Distribución de Cartera", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
        with c2:
            fig_bar = px.bar(df, x='ticker', y='Ganancia', title=f"Ganancia Absoluta ({simbolo})", color='Ganancia', color_continuous_scale='RdYlGn')
            st.plotly_chart(fig_bar, use_container_width=True)

        # TABLA
        st.subheader("Detalle de Posiciones")
        df_display = df[['fecha', 'ticker', 'cantidad', 'Costo Final', 'Valor Actual', 'Ganancia']].copy()
        df_display['fecha'] = df_display['fecha'].dt.strftime('%d-%m-%Y')
        
        # Aplicamos el formato con comas solo a la visualización de la tabla
        for col in ['Costo Final', 'Valor Actual', 'Ganancia']:
            df_display[col] = df_display[col].apply(formato_ars)
            
        st.dataframe(df_display, use_container_width=True)

    except Exception as e:
        st.error(f"Error procesando los datos financieros: {e}")
else:
    st.info("💡 Sincronizando con Google Sheets...")

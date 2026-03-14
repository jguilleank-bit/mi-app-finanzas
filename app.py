import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import requests

st.set_page_config(page_title="Terminal Inversiones Argentina", layout="wide")

# Formateador visual estilo ARS seguro
def formato_ars(valor):
    try:
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "0,00"

# API Dólar MEP en vivo
@st.cache_data(ttl=600)
def get_dolar_mep():
    try:
        url = "https://criptoya.com/api/dolar"
        resp = requests.get(url, timeout=5).json()
        return float(resp['mep']['al30']['ci']['price'])
    except Exception:
        return 1400.0

# Lector de Google Sheets
def load_data(url):
    try:
        sheet_id = url.split("/d/")[1].split("/")[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        df = pd.read_csv(csv_url)
        df.columns = df.columns.str.strip().str.lower()
        return df
    except Exception:
        return None

# Limpieza robusta de números 
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
        
        # Limpieza segura columna por columna
        df['cantidad'] = limpiar_numero(df['cantidad'])
        df['precio_unitario'] = limpiar_numero(df['precio_unitario'])
        
        if 'comision_total' in df.columns:
            df['comision_total'] = limpiar_numero(df['comision_total'])
        else:
            df['comision_total'] = 0.0
            
        if 'cotizacion_mep_dia' in df.columns:
            df['cotizacion_mep_dia'] = limpiar_numero(df['cotizacion_mep_dia'])
            df['cotizacion_mep_dia'] = df['cotizacion_mep_dia'].replace(0.0, mep_hoy)
        else:
            df['cotizacion_mep_dia'] = mep_hoy

        # Precios de Mercado
        tickers = df['ticker'].dropna().unique().tolist()
        precios_dict = {}
        with st.spinner('Obteniendo precios en vivo...'):
            for t in tickers:
                try:
                    tkr = yf.Ticker(t)
                    hist = tkr.history(period="1d")
                    if not hist.empty:
                        precios_dict[t] = float(hist['Close'].iloc[-1])
                    else:
                        precios_dict[t] = 0.0
                except Exception:
                    precios_dict[t] = 0.0

        # Cálculos de Costos
        df['costo_total_ars'] = (df['cantidad'] * df['precio_unitario']) + df['comision_total']
        df['costo_usd_compra'] = df['costo_total_ars'] / df['cotizacion_mep_dia']
        df['costo_ajustado_mep_hoy'] = df['costo_usd_compra'] * mep_hoy
        
        def get_valor_actual(row):
            p = precios_dict.get(row['ticker'], 0.0)
            return p * row['cantidad']

        df['valor_actual_ars'] = df.apply(get_valor_actual, axis=1)
        df['ganancia_real_ars'] = df['valor_actual_ars'] - df['costo_ajustado_mep_hoy']

        # Ajuste de moneda
        factor = 1.0 if moneda_view == "ARS (Pesos)" else (1.0 / mep_hoy)
        simbolo = "$" if moneda_view == "ARS (Pesos)" else "USD"

        # Métricas principales
        total_inv = df['costo_ajustado_mep_hoy'].sum() * factor
        total_mkt = df['valor_actual_ars'].sum() * factor
        rendimiento = ((total_mkt / total_inv) - 1) * 100 if total_inv > 0 else 0.0

        c1, c2, c3 = st.columns(3)
        c1.metric("Inversión Ajustada", f"{simbolo} {formato_ars(total_inv)}")
        c2.metric("Valor Cartera", f"{simbolo} {formato_ars(total_mkt)}")
        c3.metric("Rendimiento Real", f"{rendimiento:.2f}%")

        st.markdown("---")

        # Gráficos
        df_agrupado = df.groupby('ticker', as_index=False).agg({
            'valor_actual_ars': 'sum',
            'ganancia_real_ars': 'sum'
        })
        
        df_agrupado['Valor_Mostrar'] = df_agrupado['valor_actual_ars'] * factor
        df_agrupado['Ganancia_Mostrar'] = df_agrupado['ganancia_real_ars'] * factor

        g1, g2 = st.columns(2)

        with g1:
            fig_pie = px.pie(df_agrupado, values='Valor_Mostrar', names='ticker', 
                             title="Distribución de tu Cartera", hole=0.4)
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)

        with g2:
            fig_bar = px.bar(df_agrupado, x='ticker', y='Ganancia_Mostrar', 
                             title=f"Ganancia o Pérdida Real ({simbolo})",
                             color='Ganancia_Mostrar', 
                             color_continuous_scale='RdYlGn',
                             labels={'Ganancia_Mostrar': 'Ganancia', 'ticker': 'Activo'})
            st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("---")

        # Tabla de Detalles (Formateada de forma segura)
        st.subheader("Detalle de Posiciones")
        
        df_mostrar = pd.DataFrame()
        df_mostrar['Fecha'] = df['fecha'].dt.strftime('%d-%m-%Y')
        df_mostrar['Ticker'] = df['ticker']
        df_mostrar['Cant.'] = df['cantidad']
        
        def format_moneda(val):
            return f"{simbolo} {formato_ars(val * factor)}"
            
        df_mostrar['Costo Histórico'] = df['costo_total_ars'].apply(format_moneda)
        df_mostrar['Costo Ajustado (Hoy)'] = df['costo_ajustado_mep_hoy'].apply(format_moneda)
        df_mostrar['Valor Actual'] = df['valor_actual_ars'].apply(format_moneda)
        df_mostrar['Ganancia Real'] = df['ganancia_real_ars'].apply(format_moneda)

        st.dataframe(df_mostrar, use_container_width=True)

    except Exception as e:
        st.error(f"Error procesando datos: {str(e)}")
else:
    st.warning("No se detectaron datos en la hoja de cálculo.")

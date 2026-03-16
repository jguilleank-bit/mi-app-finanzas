#!/usr/bin/env python3
"""App mínima de portfolio en Streamlit usando Google Sheets."""

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Mi Portfolio", layout="wide")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"


def to_csv_export_url(sheet_url: str) -> str:
    """Convierte URL de edición de Google Sheets a URL CSV exportable."""
    marker = "/d/"
    if marker not in sheet_url:
        return sheet_url
    sheet_id = sheet_url.split(marker, 1)[1].split("/", 1)[0]
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"


def fmt_money(value: float, symbol: str) -> str:
    return f"{symbol} {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_number(value: float) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_number(v) -> float:
    """Soporta números estilo ARS: 1.234,56."""
    text = str(v).replace("$", "").strip()
    if not text or text.lower() == "nan":
        return 0.0
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except Exception:
        return 0.0


def parse_date_column(df: pd.DataFrame) -> pd.Series:
    """Busca una columna con 'fecha' y la convierte a datetime."""
    for col in df.columns:
        if "fecha" in str(col).lower():
            parsed = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
            if parsed.notna().any():
                return parsed
    return pd.Series(pd.NaT, index=df.index)


def annualize_return(ret_total: float, days_invested: float) -> float:
    if days_invested > 0 and (1 + ret_total) > 0:
        return ((1 + ret_total) ** (365 / days_invested) - 1) * 100
    return 0.0


@st.cache_data(ttl=600)
def get_mep() -> float:
    try:
        r = requests.get("https://criptoya.com/api/dolar", timeout=8)
        return float(r.json()["mep"]["al30"]["ci"]["price"])
    except Exception:
        return 1400.0


st.title("🚀 Mi Portfolio")
mep = get_mep()
currency = st.sidebar.selectbox("Moneda", ["ARS", "USD"])
symbol, fx = ("$", 1.0) if currency == "ARS" else ("USD", 1.0 / mep)

url = to_csv_export_url(SHEET_URL)

try:
    df = pd.read_csv(url)
except Exception:
    st.error("No se pudo leer la planilla. Revisá permisos de Google Sheets.")
    st.stop()

# Normaliza nombres de columnas
df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

# Columnas mínimas esperadas
required = ["ticker", "cantidad", "precio_unitario", "cotizacion_mep_dia"]
for c in required:
    if c not in df.columns:
        st.error(f"Falta columna requerida en la planilla: {c}")
        st.stop()

# Columnas para gráficos
if "tipo_activo" not in df.columns:
    df["tipo_activo"] = "Sin dato"
if "broker" not in df.columns:
    df["broker"] = "Sin dato"

# Limpieza numérica
for c in ["cantidad", "precio_unitario", "cotizacion_mep_dia"]:
    df[c] = df[c].apply(parse_number)

# Precio actual por ticker
prices = {}
for t in df["ticker"].astype(str).str.strip().unique():
    if not t or t.lower() == "nan":
        continue
    try:
        close = yf.Ticker(t).history(period="1d")["Close"].iloc[-1]
        prices[t] = float(close) * (1 if t.endswith(".BA") else mep)
    except Exception:
        prices[t] = 0.0

# Cálculos base
df["costo"] = (df["cantidad"] * df["precio_unitario"] / df["cotizacion_mep_dia"].replace(0, mep)) * mep
df["hoy"] = df.apply(lambda r: prices.get(str(r["ticker"]).strip(), 0.0) * r["cantidad"], axis=1)
df["ganancia"] = df["hoy"] - df["costo"]
df["fecha_operacion"] = parse_date_column(df)

dias = (pd.Timestamp.now().normalize() - df["fecha_operacion"]).dt.days

inversion = float(df["costo"].sum())
cartera = float(df["hoy"].sum())
ganancia = cartera - inversion
retorno_total = (cartera / inversion) - 1 if inversion > 0 else 0.0

# Tiempo de inversión total de la cartera (no promedio): desde la fecha más antigua
mask_fechas = df["fecha_operacion"].notna()
if mask_fechas.any():
    dias_cartera = float((pd.Timestamp.now().normalize() - df.loc[mask_fechas, "fecha_operacion"].min()).days)
else:
    dias_cartera = 0.0

anios_cartera = dias_cartera / 365 if dias_cartera > 0 else 0.0
rendimiento_anual = annualize_return(retorno_total, dias_cartera)

# Métricas
c1, c2, c3, c4 = st.columns(4)
c1.metric("Inversión", fmt_money(inversion * fx, symbol))
c2.metric("Cartera", fmt_money(cartera * fx, symbol), fmt_money(ganancia * fx, symbol))
c3.metric("Rendimiento anual", f"{rendimiento_anual:.2f}%")
c4.metric("Tiempo inversión cartera", f"{anios_cartera:.2f} años" if anios_cartera > 0 else "N/D")

# Gráficos 1: cartera por tipo de activo / broker
left, right = st.columns(2)

df_tipo = df.groupby("tipo_activo", dropna=False).agg(inversion=("costo", "sum"), cartera=("hoy", "sum"), ganancia=("ganancia", "sum"), fecha_inicio=("fecha_operacion", "min")).reset_index()
df_tipo["tipo_activo"] = df_tipo["tipo_activo"].astype(str)
left.plotly_chart(
    px.pie(
        df_tipo,
        values="cartera",
        names="tipo_activo",
        title="% de la cartera por tipo de activo",
        hole=0.45,
    ),
    use_container_width=True,
)

df_broker = df.groupby("broker", dropna=False).agg(cartera=("hoy", "sum")).reset_index()
df_broker["broker"] = df_broker["broker"].astype(str)
df_broker["etiqueta"] = (df_broker["cartera"] * fx).apply(fmt_number)
fig_broker = px.bar(
    df_broker,
    x="broker",
    y="cartera",
    title="Cartera por broker",
    color="broker",
    text="etiqueta",
)
fig_broker.update_traces(textposition="outside")
right.plotly_chart(fig_broker, use_container_width=True)

# Tabla resumen debajo de los 2 gráficos superiores
st.subheader("Resumen por tipo de activo")
dias_tipo = (pd.Timestamp.now().normalize() - df_tipo["fecha_inicio"]).dt.days
ret_tipo = (df_tipo["cartera"] / df_tipo["inversion"].replace(0, pd.NA) - 1).fillna(0)
df_tipo["tir_anual"] = [annualize_return(ret, d if pd.notna(d) and d > 0 else 0) for ret, d in zip(ret_tipo, dias_tipo)]

tabla_tipo_num = df_tipo.sort_values("cartera", ascending=False).copy()
tabla_tipo = pd.DataFrame(
    {
        "Tipo de activo": tabla_tipo_num["tipo_activo"],
        "Inversión": (tabla_tipo_num["inversion"] * fx).apply(lambda v: fmt_money(v, symbol)),
        "Cartera": (tabla_tipo_num["cartera"] * fx).apply(lambda v: fmt_money(v, symbol)),
        "Ganancia": (tabla_tipo_num["ganancia"] * fx).apply(lambda v: fmt_money(v, symbol)),
        "TIR anual": tabla_tipo_num["tir_anual"].map(lambda x: f"{x:.2f}%"),
    }
)

fila_total = pd.DataFrame(
    [
        {
            "Tipo de activo": "TOTAL",
            "Inversión": fmt_money(inversion * fx, symbol),
            "Cartera": fmt_money(cartera * fx, symbol),
            "Ganancia": fmt_money(ganancia * fx, symbol),
            "TIR anual": f"{rendimiento_anual:.2f}%",
        }
    ]
)

st.dataframe(pd.concat([tabla_tipo, fila_total], ignore_index=True), use_container_width=True, hide_index=True)

# Gráficos 2: cartera/ganancia por ticker
left2, right2 = st.columns(2)

df_ticker = (
    df.groupby("ticker", dropna=False)
    .agg(
        cantidad=("cantidad", "sum"),
        costo=("costo", "sum"),
        cartera=("hoy", "sum"),
        ganancia=("ganancia", "sum"),
        fecha_inicio=("fecha_operacion", "min"),
    )
    .reset_index()
)

df_ticker["ticker"] = df_ticker["ticker"].astype(str)
left2.plotly_chart(
    px.pie(
        df_ticker,
        values="cartera",
        names="ticker",
        title="% de la cartera por ticker",
        hole=0.45,
    ),
    use_container_width=True,
)

df_ticker_plot = df_ticker.sort_values("ganancia").copy()
df_ticker_plot["etiqueta"] = (df_ticker_plot["ganancia"] * fx).apply(fmt_number)
fig_gan_ticker = px.bar(
    df_ticker_plot,
    x="ticker",
    y="ganancia",
    color="ganancia",
    title="Ganancia por ticker",
    color_continuous_scale="RdYlGn",
    text="etiqueta",
)
fig_gan_ticker.update_traces(textposition="outside")
right2.plotly_chart(fig_gan_ticker, use_container_width=True)

# Tabla de posiciones solicitada
st.subheader("Mis posiciones")

dias_ticker = (pd.Timestamp.now().normalize() - df_ticker["fecha_inicio"]).dt.days
meses_ticker = (dias_ticker / 30.44).fillna(0)

df_ticker["precio_promedio"] = (df_ticker["costo"] / df_ticker["cantidad"].replace(0, pd.NA)).fillna(0)
df_ticker["precio_actual"] = (df_ticker["cartera"] / df_ticker["cantidad"].replace(0, pd.NA)).fillna(0)
retorno_ticker = (df_ticker["cartera"] / df_ticker["costo"].replace(0, pd.NA) - 1).fillna(0)
df_ticker["ganancia_pct"] = (retorno_ticker * 100).fillna(0)
df_ticker["tir_anual"] = [annualize_return(ret, d if d > 0 else 0) for ret, d in zip(retorno_ticker, dias_ticker.fillna(0))]

tabla_pos = pd.DataFrame(
    {
        "Ticker": df_ticker["ticker"],
        "Cantidad": df_ticker["cantidad"].map(lambda x: f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")),
        "Precio promedio": (df_ticker["precio_promedio"] * fx).apply(lambda v: fmt_money(v, symbol)),
        "Precio actual": (df_ticker["precio_actual"] * fx).apply(lambda v: fmt_money(v, symbol)),
        "Ganancia": (df_ticker["ganancia"] * fx).apply(lambda v: fmt_money(v, symbol)),
        "% ganancia": df_ticker["ganancia_pct"].map(lambda x: f"{x:.2f}%"),
        "Tiempo (meses)": meses_ticker.map(lambda x: f"{x:.1f}"),
        "TIR anual": df_ticker["tir_anual"].map(lambda x: f"{x:.2f}%"),
    }
)

st.dataframe(tabla_pos.sort_values("Ticker"), use_container_width=True, hide_index=True)

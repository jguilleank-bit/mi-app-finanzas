#!/usr/bin/env python3
"""App mínima de portfolio en Streamlit usando Google Sheets."""

import pandas as pd
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
cmepsafe = df["cotizacion_mep_dia"].replace(0, mep)
df["costo"] = (df["cantidad"] * df["precio_unitario"] / cmepsafe) * mep
df["hoy"] = df.apply(lambda r: prices.get(str(r["ticker"]).strip(), 0.0) * r["cantidad"], axis=1)
df["ganancia"] = df["hoy"] - df["costo"]

inversion = float(df["costo"].sum())
cartera = float(df["hoy"].sum())
ganancia = cartera - inversion
retorno_total = (cartera / inversion) - 1 if inversion > 0 else 0.0

# Promedio de días invertidos (ponderado por costo)
df["fecha_operacion"] = parse_date_column(df)
dias = (pd.Timestamp.now().normalize() - df["fecha_operacion"]).dt.days
validos = df["fecha_operacion"].notna() & (df["costo"] > 0) & dias.notna() & (dias >= 0)
if validos.any():
    tiempo_promedio_dias = float((dias[validos] * df.loc[validos, "costo"]).sum() / df.loc[validos, "costo"].sum())
else:
    tiempo_promedio_dias = 0.0

# Rendimiento anual (anualización por promedio de días)
if tiempo_promedio_dias > 0 and (1 + retorno_total) > 0:
    rendimiento_anual = ((1 + retorno_total) ** (365 / tiempo_promedio_dias) - 1) * 100
else:
    rendimiento_anual = 0.0

# Orden solicitado: Inversión -> Cartera -> Rendimiento anual -> Tiempo promedio
c1, c2, c3, c4 = st.columns(4)
c1.metric("Inversión", fmt_money(inversion * fx, symbol))
c2.metric("Cartera", fmt_money(cartera * fx, symbol), fmt_money(ganancia * fx, symbol))
c3.metric("Rendimiento anual", f"{rendimiento_anual:.2f}%")
c4.metric("Tiempo promedio inversión", f"{tiempo_promedio_dias:.0f} días" if tiempo_promedio_dias > 0 else "N/D")

st.subheader("Detalle")
show = df[["ticker", "cantidad", "precio_unitario", "costo", "hoy", "ganancia"]].copy()
for c in ["precio_unitario", "costo", "hoy", "ganancia"]:
    show[c] = show[c] * fx
st.dataframe(show, use_container_width=True, hide_index=True)

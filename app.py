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


def annualize_return(ret_total: float, avg_days: float) -> float:
    if avg_days > 0 and (1 + ret_total) > 0:
        return ((1 + ret_total) ** (365 / avg_days) - 1) * 100
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

# Columnas para resumen/gráficos
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

validos = df["fecha_operacion"].notna() & (df["costo"] > 0) & dias.notna() & (dias >= 0)
if validos.any():
    tiempo_promedio_dias = float((dias[validos] * df.loc[validos, "costo"]).sum() / df.loc[validos, "costo"].sum())
else:
    tiempo_promedio_dias = 0.0

rendimiento_anual = annualize_return(retorno_total, tiempo_promedio_dias)

# Orden solicitado: Inversión -> Cartera -> Rendimiento anual -> Tiempo promedio
c1, c2, c3, c4 = st.columns(4)
c1.metric("Inversión", fmt_money(inversion * fx, symbol))
c2.metric("Cartera", fmt_money(cartera * fx, symbol), fmt_money(ganancia * fx, symbol))
c3.metric("Rendimiento anual", f"{rendimiento_anual:.2f}%")
c4.metric("Tiempo promedio inversión", f"{tiempo_promedio_dias:.0f} días" if tiempo_promedio_dias > 0 else "N/D")

# Gráficos solicitados
left, right = st.columns(2)

df_tipo = df.groupby("tipo_activo", dropna=False).agg(inversion=("costo", "sum"), cartera=("hoy", "sum"), ganancia=("ganancia", "sum")).reset_index()
df_tipo["tipo_activo"] = df_tipo["tipo_activo"].astype(str)

left.plotly_chart(
    px.pie(
        df_tipo,
        values="inversion",
        names="tipo_activo",
        title="Porcentaje de inversión por tipo de activo",
        hole=0.45,
    ),
    use_container_width=True,
)

df_broker = df.groupby("broker", dropna=False).agg(inversion=("costo", "sum")).reset_index()
df_broker["broker"] = df_broker["broker"].astype(str)
right.plotly_chart(
    px.bar(
        df_broker,
        x="broker",
        y="inversion",
        title="Inversión por broker",
        color="broker",
    ),
    use_container_width=True,
)

# Tabla resumen solicitada
st.subheader("Resumen por tipo de activo")

rows = []
for tipo, dft in df.groupby("tipo_activo", dropna=False):
    inv_t = float(dft["costo"].sum())
    car_t = float(dft["hoy"].sum())
    gan_t = car_t - inv_t
    ret_t = (car_t / inv_t) - 1 if inv_t > 0 else 0.0

    dias_t = (pd.Timestamp.now().normalize() - dft["fecha_operacion"]).dt.days
    mask_t = dft["fecha_operacion"].notna() & (dft["costo"] > 0) & dias_t.notna() & (dias_t >= 0)
    if mask_t.any():
        prom_dias_t = float((dias_t[mask_t] * dft.loc[mask_t, "costo"]).sum() / dft.loc[mask_t, "costo"].sum())
    else:
        prom_dias_t = 0.0

    tir_anual_t = annualize_return(ret_t, prom_dias_t)

    rows.append(
        {
            "Tipo de activo": str(tipo),
            "Cartera": fmt_money(car_t * fx, symbol),
            "Inversión": fmt_money(inv_t * fx, symbol),
            "Ganancia": fmt_money(gan_t * fx, symbol),
            "TIR anual": f"{tir_anual_t:.2f}%",
        }
    )

resumen_df = pd.DataFrame(rows).sort_values("Tipo de activo")
st.dataframe(resumen_df, use_container_width=True, hide_index=True)

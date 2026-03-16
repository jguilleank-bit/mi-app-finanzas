1	#!/usr/bin/env python3
     2	"""App mínima de portfolio en Streamlit usando Google Sheets."""
     3	
     4	import pandas as pd
     5	import requests
     6	import streamlit as st
     7	import yfinance as yf
     8	
     9	st.set_page_config(page_title="Mi Portfolio", layout="wide")
    10	
    11	SHEET_URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"
    12	
    13	
    14	def to_csv_export_url(sheet_url: str) -> str:
    15	    """Convierte URL de edición de Google Sheets a URL CSV exportable."""
    16	    marker = "/d/"
    17	    if marker not in sheet_url:
    18	        return sheet_url
    19	    sheet_id = sheet_url.split(marker, 1)[1].split("/", 1)[0]
    20	    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    21	
    22	
    23	def fmt_money(value: float, symbol: str) -> str:
    24	    return f"{symbol} {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    25	
    26	
    27	def parse_number(v) -> float:
    28	    """Soporta números estilo ARS: 1.234,56"""
    29	    text = str(v).replace("$", "").strip()
    30	    if not text or text.lower() == "nan":
    31	        return 0.0
    32	    text = text.replace(".", "").replace(",", ".")
    33	    try:
    34	        return float(text)
    35	    except Exception:
    36	        return 0.0
    37	
    38	
    39	@st.cache_data(ttl=600)
    40	def get_mep() -> float:
    41	    try:
    42	        r = requests.get("https://criptoya.com/api/dolar", timeout=8)
    43	        return float(r.json()["mep"]["al30"]["ci"]["price"])
    44	    except Exception:
    45	        return 1400.0
    46	
    47	
    48	st.title("🚀 Mi Portfolio")
    49	mep = get_mep()
    50	currency = st.sidebar.selectbox("Moneda", ["ARS", "USD"])
    51	symbol, fx = ("$", 1.0) if currency == "ARS" else ("USD", 1.0 / mep)
    52	
    53	url = to_csv_export_url(SHEET_URL)
    54	
    55	try:
    56	    df = pd.read_csv(url)
    57	except Exception:
    58	    st.error("No se pudo leer la planilla. Revisá permisos de Google Sheets.")
    59	    st.stop()
    60	
    61	# Normaliza nombres de columnas
    62	cols = {c: str(c).strip().lower().replace(" ", "_") for c in df.columns}
    63	df = df.rename(columns=cols)
    64	
    65	# Columnas mínimas esperadas
    66	required = ["ticker", "cantidad", "precio_unitario", "cotizacion_mep_dia"]
    67	for c in required:
    68	    if c not in df.columns:
    69	        st.error(f"Falta columna requerida en la planilla: {c}")
    70	        st.stop()
    71	
    72	# Limpieza numérica
    73	for c in ["cantidad", "precio_unitario", "cotizacion_mep_dia"]:
    74	    df[c] = df[c].apply(parse_number)
    75	
    76	# Precio actual por ticker
    77	prices = {}
    78	for t in df["ticker"].astype(str).str.strip().unique():
    79	    if not t:
    80	        continue
    81	    try:
    82	        close = yf.Ticker(t).history(period="1d")["Close"].iloc[-1]
    83	        prices[t] = float(close) * (1 if t.endswith(".BA") else mep)
    84	    except Exception:
    85	        prices[t] = 0.0
    86	
    87	# Cálculos base
    88	cmepsafe = df["cotizacion_mep_dia"].replace(0, mep)
    89	df["costo"] = (df["cantidad"] * df["precio_unitario"] / cmepsafe) * mep
    90	df["hoy"] = df.apply(lambda r: prices.get(str(r["ticker"]).strip(), 0.0) * r["cantidad"], axis=1)
    91	df["ganancia"] = df["hoy"] - df["costo"]
    92	
    93	inversion = float(df["costo"].sum())
    94	cartera = float(df["hoy"].sum())
    95	ganancia = cartera - inversion
    96	tir_total = ((cartera / inversion) - 1) * 100 if inversion > 0 else 0.0
    97	
    98	# Orden solicitado: Inversión -> Cartera -> TIR
    99	c1, c2, c3 = st.columns(3)
   100	c1.metric("Inversión", fmt_money(inversion * fx, symbol))
   101	c2.metric("Cartera", fmt_money(cartera * fx, symbol), fmt_money(ganancia * fx, symbol))
   102	c3.metric("TIR Total", f"{tir_total:.2f}%")
   103	
   104	st.subheader("Detalle")
   105	show = df[["ticker", "cantidad", "precio_unitario", "costo", "hoy", "ganancia"]].copy()
   106	for c in ["precio_unitario", "costo", "hoy", "ganancia"]:
   107	    show[c] = show[c] * fx
   108	st.dataframe(show, use_container_width=True, hide_index=True)

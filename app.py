 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/app.py b/app.py
index 689b6b5b7bb157b366c269969beca1523fa3508f..d2b7a16548e86ddc98f23e865f5d7fe121d9241f 100644
--- a/app.py
+++ b/app.py
@@ -1,78 +1,202 @@
-import streamlit as st
 import pandas as pd
-import yfinance as yf
-import plotly.express as px
 import requests
+import streamlit as st
+import yfinance as yf
+
+st.set_page_config(page_title="Mi Inversión y TIR", layout="wide")
 
-st.set_page_config(page_title="Portfolio Pro", layout="wide")
+SHEET_URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"
 
-# 1. FUNCIONES DE APOYO
-def fmt_mon(v, s):
+
+def format_money(value: float, symbol: str) -> str:
     try:
-        vf = f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
-        return f"{s} {vf}"
-    except: return f"{s} 0,00"
+        return f"{symbol} {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
+    except Exception:
+        return f"{symbol} 0,00"
+
+
+def to_float(value) -> float:
+    if pd.isna(value) or value == "":
+        return 0.0
+    normalized = str(value).strip().replace("$", "").replace(" ", "")
+    normalized = normalized.replace(".", "").replace(",", ".")
+    try:
+        return float(normalized)
+    except Exception:
+        return 0.0
+
+
+def detect_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
+    for alias in aliases:
+        if alias in df.columns:
+            return alias
+    return None
 
-def clean_px(v):
-    if pd.isna(v) or v == "": return 0.0
-    s = str(v).replace("$", "").replace(".", "").replace(",", ".").strip()
-    try: return float(s)
-    except: return 0.0
 
 @st.cache_data(ttl=600)
-def get_mep():
+def get_mep() -> float:
     try:
-        return float(requests.get("https://criptoya.com/api/dolar").json()['mep']['al30']['ci']['price'])
-    except: return 1400.0
+        response = requests.get("https://criptoya.com/api/dolar", timeout=10)
+        response.raise_for_status()
+        return float(response.json()["mep"]["al30"]["ci"]["price"])
+    except Exception:
+        return 1400.0
+
 
-def load_data(url):
+@st.cache_data(ttl=300)
+def load_sheet(url: str) -> pd.DataFrame | None:
     try:
-        sid = url.split("/d/")[1].split("/")[0]
-        df = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv")
+        sheet_id = url.split("/d/")[1].split("/")[0]
+        export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
+        df = pd.read_csv(export_url)
         df.columns = df.columns.str.strip().str.lower()
         return df
-    except: return None
+    except Exception:
+        return None
+
+
+def load_live_prices(tickers: list[str], mep: float) -> dict[str, float]:
+    prices: dict[str, float] = {}
+    for ticker in tickers:
+        try:
+            history = yf.Ticker(ticker).history(period="1d")
+            close = float(history["Close"].iloc[-1])
+            prices[ticker] = close if ticker.endswith(".BA") else close * mep
+        except Exception:
+            prices[ticker] = 0.0
+    return prices
+
+
+def build_portfolio(df: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
+    mep = get_mep()
+
+    col_cantidad = detect_column(df, ["cantidad", "qty", "units"])
+    col_precio_compra = detect_column(df, ["precio_unitario", "precio compra", "precio_compra", "buy_price"])
+    col_precio_actual = detect_column(df, ["precio_actual", "precio hoy", "precio_hoy", "market_price"])
+    col_ticker = detect_column(df, ["ticker", "simbolo", "symbol"])
+    col_tipo = detect_column(df, ["tipo_activo", "tipo", "tipo de activo", "asset_type", "clase"])
+
+    if col_cantidad is None or col_precio_compra is None:
+        return pd.DataFrame(), "Faltan columnas obligatorias: 'cantidad' y/o 'precio_unitario'."
+
+    result = df.copy()
+    result[col_cantidad] = result[col_cantidad].apply(to_float)
+    result[col_precio_compra] = result[col_precio_compra].apply(to_float)
+
+    if col_precio_actual is not None:
+        result[col_precio_actual] = result[col_precio_actual].apply(to_float)
+        result["precio_actual_ars"] = result[col_precio_actual]
+    else:
+        if col_ticker is None:
+            return pd.DataFrame(), "No hay 'precio_actual' ni 'ticker' para valuar la cartera."
+        tickers = [t for t in result[col_ticker].dropna().astype(str).unique() if t.strip()]
+        live_prices = load_live_prices(tickers, mep)
+        result["precio_actual_ars"] = result[col_ticker].astype(str).map(live_prices).fillna(0.0)
+
+    result["inversion_ars"] = result[col_cantidad] * result[col_precio_compra]
+    result["valor_actual_ars"] = result[col_cantidad] * result["precio_actual_ars"]
+    result["ganancia_ars"] = result["valor_actual_ars"] - result["inversion_ars"]
+
+    if col_tipo is None:
+        result["tipo_activo"] = "Sin clasificar"
+        col_tipo = "tipo_activo"
+    else:
+        result[col_tipo] = result[col_tipo].fillna("Sin clasificar").replace("", "Sin clasificar")
+
+    result["tipo_activo"] = result[col_tipo]
+    return result, None
+
+
+st.title("📈 Mi Inversión y TIR")
+st.caption("Visualización automática desde Google Sheets")
+
+currency = st.sidebar.selectbox("Moneda", ["ARS", "USD"], index=0)
+df_raw = load_sheet(SHEET_URL)
+
+if df_raw is None or df_raw.empty:
+    st.error("No se pudo cargar la hoja de cálculo.")
+    st.stop()
+
+portfolio, error = build_portfolio(df_raw)
+if error:
+    st.error(error)
+    st.dataframe(df_raw.head(20), use_container_width=True)
+    st.stop()
 
-# 2. INICIO Y DATOS
-st.title("🚀 Mi Portfolio de Inversiones")
-URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"
 mep = get_mep()
+factor = 1.0 if currency == "ARS" else (1.0 / mep)
+symbol = "$" if currency == "ARS" else "USD"
+
+inversion_total = float(portfolio["inversion_ars"].sum())
+valor_total = float(portfolio["valor_actual_ars"].sum())
+ganancia_total = valor_total - inversion_total
+tir_total = ((valor_total / inversion_total) - 1) * 100 if inversion_total > 0 else 0.0
+
+c1, c2, c3 = st.columns(3)
+c1.metric("Inversión total", format_money(inversion_total * factor, symbol))
+c2.metric("Valor actual", format_money(valor_total * factor, symbol), delta=format_money(ganancia_total * factor, symbol))
+c3.metric("TIR total", f"{tir_total:.2f}%")
+
+st.markdown("---")
+st.subheader("Resumen por tipo de activo")
+
+summary = (
+    portfolio.groupby("tipo_activo", as_index=False)
+    .agg(
+        inversion_ars=("inversion_ars", "sum"),
+        valor_actual_ars=("valor_actual_ars", "sum"),
+        ganancia_ars=("ganancia_ars", "sum"),
+    )
+    .sort_values("valor_actual_ars", ascending=False)
+)
+summary["tir_%"] = summary.apply(
+    lambda row: ((row["valor_actual_ars"] / row["inversion_ars"]) - 1) * 100 if row["inversion_ars"] > 0 else 0,
+    axis=1,
+)
+
+summary_view = summary.rename(
+    columns={
+        "tipo_activo": "Tipo de activo",
+        "inversion_ars": "Inversión",
+        "valor_actual_ars": "Valor actual",
+        "ganancia_ars": "Ganancia",
+        "tir_%": "TIR %",
+    }
+)
+
+for col in ["Inversión", "Valor actual", "Ganancia"]:
+    summary_view[col] = summary_view[col] * factor
+
+st.dataframe(
+    summary_view,
+    use_container_width=True,
+    hide_index=True,
+    column_config={
+        "Inversión": st.column_config.NumberColumn(format=f"{symbol} %.2f"),
+        "Valor actual": st.column_config.NumberColumn(format=f"{symbol} %.2f"),
+        "Ganancia": st.column_config.NumberColumn(format=f"{symbol} %.2f"),
+        "TIR %": st.column_config.NumberColumn(format="%.2f%%"),
+    },
+)
+
+st.subheader("Detalle de posiciones")
+columns_to_show = [
+    c
+    for c in ["ticker", "tipo_activo", "inversion_ars", "valor_actual_ars", "ganancia_ars"]
+    if c in portfolio.columns
+]
+detail = portfolio[columns_to_show].copy()
+rename_map = {
+    "ticker": "Ticker",
+    "tipo_activo": "Tipo de activo",
+    "inversion_ars": "Inversión",
+    "valor_actual_ars": "Valor actual",
+    "ganancia_ars": "Ganancia",
+}
+detail = detail.rename(columns=rename_map)
+
+for col in ["Inversión", "Valor actual", "Ganancia"]:
+    if col in detail.columns:
+        detail[col] = detail[col] * factor
 
-moneda = st.sidebar.selectbox("Moneda:", ["ARS (Pesos)", "USD (Dólares)"])
-simb, fact = ("$", 1.0) if moneda == "ARS (Pesos)" else ("USD", 1.0/mep)
-
-df_raw = load_data(URL)
-
-if df_raw is not None and not df_raw.empty:
-    df = df_raw.copy()
-    for col in ['cantidad', 'precio_unitario', 'cotizacion_mep_dia']:
-        df[col] = df[col].apply(clean_px)
-    
-    # Precios en Vivo
-    tkrs = df['ticker'].unique()
-    px_vivos = {}
-    with st.spinner('Sincronizando...'):
-        for t in tkrs:
-            try:
-                h = yf.Ticker(t).history(period="1d")
-                p = float(h['Close'].iloc[-1])
-                px_vivos[t] = p if t.endswith(".BA") else p * mep
-            except: px_vivos[t] = 0.0
-
-    # Cálculos
-    df['costo_ars'] = (df['cantidad'] * df['precio_unitario'] / df['cotizacion_mep_dia'].replace(0, mep)) * mep
-    df['val_hoy_ars'] = df.apply(lambda r: px_vivos.get(r['ticker'], 0) * r['cantidad'], axis=1)
-    df['gan_ars'] = df['val_hoy_ars'] - df['costo_ars']
-
-    # 3. MÉTRICAS TOP (Restauradas)
-    inv_t, val_t = df['costo_ars'].sum(), df['val_hoy_ars'].sum()
-    gan_t = val_t - inv_t
-    tir_t = ((val_t / inv_t) - 1) * 100 if inv_t > 0 else 0
-
-    c1, c2, c3 = st.columns(3)
-    c1.metric("Valor Cartera", fmt_mon(val_t*fact, simb), f"{fmt_mon(gan_t*fact, simb)}")
-    c2.metric("Inversión Ajustada", fmt_mon(inv_t*fact, simb))
-    c3.metric("Rendimiento Total (TIR)", f"{tir_t:.2f}%")
-    st.markdown("---")
-
-    # 4. TABLA CON
+st.dataframe(detail, use_container_width=True, hide_index=True)
 
EOF
)

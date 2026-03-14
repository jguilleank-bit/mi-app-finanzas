 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/app.py b/app.py
index 689b6b5b7bb157b366c269969beca1523fa3508f..5a68d525775cc458ba25dd673b62ecf0cc981503 100644
--- a/app.py
+++ b/app.py
@@ -1,78 +1,165 @@
 import streamlit as st
 import pandas as pd
 import yfinance as yf
-import plotly.express as px
 import requests
 
 st.set_page_config(page_title="Portfolio Pro", layout="wide")
 
+
 # 1. FUNCIONES DE APOYO
+
 def fmt_mon(v, s):
     try:
         vf = f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
         return f"{s} {vf}"
-    except: return f"{s} 0,00"
+    except Exception:
+        return f"{s} 0,00"
+
 
 def clean_px(v):
-    if pd.isna(v) or v == "": return 0.0
+    if pd.isna(v) or v == "":
+        return 0.0
     s = str(v).replace("$", "").replace(".", "").replace(",", ".").strip()
-    try: return float(s)
-    except: return 0.0
+    try:
+        return float(s)
+    except Exception:
+        return 0.0
+
 
 @st.cache_data(ttl=600)
 def get_mep():
     try:
-        return float(requests.get("https://criptoya.com/api/dolar").json()['mep']['al30']['ci']['price'])
-    except: return 1400.0
+        return float(requests.get("https://criptoya.com/api/dolar", timeout=10).json()["mep"]["al30"]["ci"]["price"])
+    except Exception:
+        return 1400.0
+
 
 def load_data(url):
     try:
         sid = url.split("/d/")[1].split("/")[0]
         df = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv")
         df.columns = df.columns.str.strip().str.lower()
         return df
-    except: return None
+    except Exception:
+        return None
+
+
+def detect_columna_tipo_activo(df):
+    candidatas = ["tipo_activo", "tipo de activo", "tipo", "asset_type", "clase"]
+    for c in candidatas:
+        if c in df.columns:
+            return c
+    return None
+
 
 # 2. INICIO Y DATOS
 st.title("🚀 Mi Portfolio de Inversiones")
 URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"
 mep = get_mep()
 
 moneda = st.sidebar.selectbox("Moneda:", ["ARS (Pesos)", "USD (Dólares)"])
-simb, fact = ("$", 1.0) if moneda == "ARS (Pesos)" else ("USD", 1.0/mep)
+simb, fact = ("$", 1.0) if moneda == "ARS (Pesos)" else ("USD", 1.0 / mep)
 
 df_raw = load_data(URL)
 
 if df_raw is not None and not df_raw.empty:
     df = df_raw.copy()
-    for col in ['cantidad', 'precio_unitario', 'cotizacion_mep_dia']:
-        df[col] = df[col].apply(clean_px)
-    
+
+    for col in ["cantidad", "precio_unitario", "cotizacion_mep_dia"]:
+        if col in df.columns:
+            df[col] = df[col].apply(clean_px)
+        else:
+            df[col] = 0.0
+
     # Precios en Vivo
-    tkrs = df['ticker'].unique()
+    tkrs = df["ticker"].dropna().unique() if "ticker" in df.columns else []
     px_vivos = {}
-    with st.spinner('Sincronizando...'):
+    with st.spinner("Sincronizando..."):
         for t in tkrs:
             try:
                 h = yf.Ticker(t).history(period="1d")
-                p = float(h['Close'].iloc[-1])
+                p = float(h["Close"].iloc[-1])
                 px_vivos[t] = p if t.endswith(".BA") else p * mep
-            except: px_vivos[t] = 0.0
+            except Exception:
+                px_vivos[t] = 0.0
 
     # Cálculos
-    df['costo_ars'] = (df['cantidad'] * df['precio_unitario'] / df['cotizacion_mep_dia'].replace(0, mep)) * mep
-    df['val_hoy_ars'] = df.apply(lambda r: px_vivos.get(r['ticker'], 0) * r['cantidad'], axis=1)
-    df['gan_ars'] = df['val_hoy_ars'] - df['costo_ars']
+    df["costo_ars"] = (
+        (df["cantidad"] * df["precio_unitario"] / df["cotizacion_mep_dia"].replace(0, mep)) * mep
+    )
+    df["val_hoy_ars"] = df.apply(lambda r: px_vivos.get(r.get("ticker", ""), 0) * r["cantidad"], axis=1)
+    df["gan_ars"] = df["val_hoy_ars"] - df["costo_ars"]
 
-    # 3. MÉTRICAS TOP (Restauradas)
-    inv_t, val_t = df['costo_ars'].sum(), df['val_hoy_ars'].sum()
+    # 3. MÉTRICAS TOP
+    inv_t, val_t = df["costo_ars"].sum(), df["val_hoy_ars"].sum()
     gan_t = val_t - inv_t
     tir_t = ((val_t / inv_t) - 1) * 100 if inv_t > 0 else 0
 
     c1, c2, c3 = st.columns(3)
-    c1.metric("Valor Cartera", fmt_mon(val_t*fact, simb), f"{fmt_mon(gan_t*fact, simb)}")
-    c2.metric("Inversión Ajustada", fmt_mon(inv_t*fact, simb))
+    c1.metric("Valor Cartera", fmt_mon(val_t * fact, simb), f"{fmt_mon(gan_t * fact, simb)}")
+    c2.metric("Inversión Ajustada", fmt_mon(inv_t * fact, simb))
     c3.metric("Rendimiento Total (TIR)", f"{tir_t:.2f}%")
     st.markdown("---")
 
-    # 4. TABLA CON
+    # 4. TABLA RESUMEN POR TIPO DE ACTIVO
+    st.subheader("📊 Resumen de inversiones por tipo de activo")
+    tipo_col = detect_columna_tipo_activo(df)
+
+    if tipo_col is None:
+        st.info(
+            "No se encontró una columna de tipo de activo. "
+            "Agregá una columna llamada 'tipo_activo' (o 'tipo') para ver este resumen."
+        )
+    else:
+        df[tipo_col] = df[tipo_col].fillna("Sin clasificar").replace("", "Sin clasificar")
+
+        resumen = (
+            df.groupby(tipo_col, dropna=False, as_index=False)
+            .agg(
+                inversion_ars=("costo_ars", "sum"),
+                valor_actual_ars=("val_hoy_ars", "sum"),
+                ganancia_ars=("gan_ars", "sum"),
+            )
+            .sort_values("valor_actual_ars", ascending=False)
+        )
+
+        resumen["rendimiento_%"] = resumen.apply(
+            lambda r: ((r["valor_actual_ars"] / r["inversion_ars"]) - 1) * 100
+            if r["inversion_ars"] > 0
+            else 0,
+            axis=1,
+        )
+        resumen["participacion_%"] = (
+            (resumen["valor_actual_ars"] / resumen["valor_actual_ars"].sum()) * 100
+            if resumen["valor_actual_ars"].sum() > 0
+            else 0
+        )
+
+        resumen_view = resumen.rename(
+            columns={
+                tipo_col: "Tipo de activo",
+                "inversion_ars": "Inversión",
+                "valor_actual_ars": "Valor actual",
+                "ganancia_ars": "Ganancia",
+                "rendimiento_%": "Rendimiento %",
+                "participacion_%": "Participación %",
+            }
+        )
+
+        for col in ["Inversión", "Valor actual", "Ganancia"]:
+            resumen_view[col] = resumen_view[col] * fact
+
+        st.dataframe(
+            resumen_view,
+            use_container_width=True,
+            hide_index=True,
+            column_config={
+                "Inversión": st.column_config.NumberColumn(format=f"{simb} %.2f"),
+                "Valor actual": st.column_config.NumberColumn(format=f"{simb} %.2f"),
+                "Ganancia": st.column_config.NumberColumn(format=f"{simb} %.2f"),
+                "Rendimiento %": st.column_config.NumberColumn(format="%.2f%%"),
+                "Participación %": st.column_config.NumberColumn(format="%.2f%%"),
+            },
+        )
+else:
+    st.error("No se pudieron cargar datos desde Google Sheets.")
 
EOF
)

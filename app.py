 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/app.py b/app.py
index 1a5fd5440a3d020105a160a22241c02807a678f6..9cb19c8608b0f1fbcaaaf9d62fb42cb74697dc33 100644
--- a/app.py
+++ b/app.py
@@ -1,62 +1,160 @@
-import streamlit as st
+import unicodedata
+
 import pandas as pd
-import yfinance as yf
 import plotly.express as px
 import requests
+import streamlit as st
+import yfinance as yf
 
 st.set_page_config(page_title="Portfolio Pro", layout="wide")
 
+SHEET_URL = "https://docs.google.com/spreadsheets/d/1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk/edit?usp=sharing"
+
+
 def fmt(v, s):
     return f"{s} {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
 
+
 def clean(v):
-    return float(str(v).replace("$","").replace(".","").replace(",",".").strip() or 0)
+    return float(str(v).replace("$", "").replace(".", "").replace(",", ".").strip() or 0)
+
+
+def normalize_col(name):
+    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("utf-8")
+    return s.strip().lower().replace(" ", "_")
+
+
+def parse_date_column(df):
+    candidates = [c for c in df.columns if "fecha" in c]
+    if not candidates:
+        return pd.Series(pd.NaT, index=df.index)
+
+    for col in candidates:
+        parsed = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
+        if parsed.notna().any():
+            return parsed
+
+    return pd.Series(pd.NaT, index=df.index)
+
+
+def to_csv_export_url(sheet_url):
+    marker = "/d/"
+    if marker in sheet_url:
+        sheet_id = sheet_url.split(marker, 1)[1].split("/", 1)[0]
+        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
+    return sheet_url
+
 
 @st.cache_data(ttl=600)
 def get_mep():
-    try: return float(requests.get("https://criptoya.com/api/dolar").json()['mep']['al30']['ci']['price'])
-    except: return 1400.0
+    try:
+        return float(requests.get("https://criptoya.com/api/dolar", timeout=8).json()["mep"]["al30"]["ci"]["price"])
+    except:
+        return 1400.0
+
 
 st.title("🚀 Mi Portfolio")
 mep = get_mep()
 mon = st.sidebar.selectbox("Moneda", ["ARS", "USD"])
-s, f = ("$", 1.0) if mon == "ARS" else ("USD", 1.0/mep)
+s, f = ("$", 1.0) if mon == "ARS" else ("USD", 1.0 / mep)
+
+url = to_csv_export_url(SHEET_URL)
 
 try:
-    sid = "1dHJGbVWBAhLCiIQgiiWB4iEMt_39ZzXIVw3Cirl8clk"
-    df = pd.read_csv(f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv")
-    df.columns = df.columns.str.strip().str.lower()
-    for c in ['cantidad','precio_unitario','cotizacion_mep_dia']: df[c] = df[c].apply(clean)
-    
-    px_v = {}
-    for t in df['ticker'].unique():
-        try: px_v[t] = yf.Ticker(t).history(period="1d")['Close'].iloc[-1] * (1 if t.endswith(".BA") else mep)
-        except: px_v[t] = 0
-    
-    df['costo'] = (df['cantidad']*df['precio_unitario']/df['cotizacion_mep_dia'].replace(0,mep))*mep
-    df['hoy'] = df.apply(lambda r: px_v.get(r['ticker'],0)*r['cantidad'], axis=1)
-    df['gan'] = df['hoy'] - df['costo']
-
-    it, vt = df['costo'].sum(), df['hoy'].sum()
-    gt, tir = vt-it, ((vt/it)-1)*100 if it>0 else 0
-
-    c1, c2, c3 = st.columns(3)
-    c1.metric("Cartera", fmt(vt*f, s), fmt(gt*f, s))
-    c2.metric("Inversión", fmt(it*f, s))
-    c3.metric("TIR Total", f"{tir:.2f}%")
-
-    st.subheader("📊 Resumen")
-    dg = df.groupby('tipo_activo').agg({'costo':'sum','hoy':'sum','gan':'sum'}).reset_index()
-    vt_tab = pd.DataFrame({'Tipo':dg['tipo_activo'].str.upper(), 'Inversión':(dg['costo']*f).apply(lambda x: fmt(x,s)), 'Valor':(dg['hoy']*f).apply(lambda x: fmt(x,s)), 'Rend':((dg['hoy']/dg['costo']-1)*100).map("{:.1f}%".format)})
-    st.dataframe(pd.concat([vt_tab, pd.DataFrame({'Tipo':['TOTAL'],'Inversión':[fmt(it*f,s)],'Valor':[fmt(vt*f,s)],'Rend':[f"{tir:.1f}%"]})]), hide_index=True, use_container_width=True)
-
-    g1, g2 = st.columns(2)
-    g1.plotly_chart(px.pie(dg, values='hoy', names='tipo_activo', title="Tipos", hole=.5), use_container_width=True)
-    db = df.groupby('broker')['hoy'].sum().reset_index()
-    g2.plotly_chart(px.bar(db, x='broker', y=db['hoy']*f, color='broker', title="Broker"), use_container_width=True)
-
-    g3, g4 = st.columns(2)
-    dt = df.groupby('ticker').agg({'hoy':'sum','gan':'sum'}).reset_index()
-    g3.plotly_chart(px.pie(dt, values='hoy', names='ticker', title="Tickers", hole=.4), use_container_width=True)
-    g4.plotly_chart(px.bar(dt.sort_values('gan'), x='ticker', y=dt['gan']*f, color='gan', title="Ganancia/Pérdida", color_continuous_scale='RdYlGn'), use_container_width=True)
-except Exception as e: st.error("Error de datos")
+    df = pd.read_csv(url)
+except Exception:
+    st.error("Error al leer la planilla de datos")
+    st.stop()
+
+df.columns = [normalize_col(c) for c in df.columns]
+
+for needed in ["ticker", "cantidad", "precio_unitario", "cotizacion_mep_dia", "tipo_activo", "broker"]:
+    if needed not in df.columns:
+        df[needed] = 0 if needed in {"cantidad", "precio_unitario", "cotizacion_mep_dia"} else "Sin dato"
+
+for c in ["cantidad", "precio_unitario", "cotizacion_mep_dia"]:
+    df[c] = df[c].apply(clean)
+
+px_v = {}
+for t in df["ticker"].astype(str).unique():
+    if not t or t.lower() == "nan":
+        continue
+    try:
+        px_v[t] = yf.Ticker(t).history(period="1d")["Close"].iloc[-1] * (1 if t.endswith(".BA") else mep)
+    except:
+        px_v[t] = 0
+
+df["costo"] = (df["cantidad"] * df["precio_unitario"] / df["cotizacion_mep_dia"].replace(0, mep)) * mep
+df["hoy"] = df.apply(lambda r: px_v.get(str(r["ticker"]), 0) * r["cantidad"], axis=1)
+df["gan"] = df["hoy"] - df["costo"]
+
+df["fecha_operacion"] = parse_date_column(df)
+dias = (pd.Timestamp.now().normalize() - df["fecha_operacion"]).dt.days.clip(lower=0)
+
+it, vt = df["costo"].sum(), df["hoy"].sum()
+gt = vt - it
+retorno_total = (vt / it) - 1 if it > 0 else 0
+tir = retorno_total * 100
+
+mask_valid_days = df["fecha_operacion"].notna() & (df["costo"] > 0)
+if mask_valid_days.any():
+    promedio_dias = (dias[mask_valid_days] * df.loc[mask_valid_days, "costo"]).sum() / df.loc[mask_valid_days, "costo"].sum()
+else:
+    promedio_dias = 0
+
+tir_anual = ((1 + retorno_total) ** (365 / promedio_dias) - 1) * 100 if promedio_dias > 0 and (1 + retorno_total) > 0 else 0
+
+c1, c2, c3, c4, c5 = st.columns(5)
+c1.metric("Inversión", fmt(it * f, s))
+c2.metric("Cartera", fmt(vt * f, s), fmt(gt * f, s))
+c3.metric("TIR Total", f"{tir:.2f}%")
+c4.metric("TIR Anual", f"{tir_anual:.2f}%")
+c5.metric("Promedio días", f"{promedio_dias:.0f} días" if promedio_dias > 0 else "N/D")
+
+st.subheader("📊 Resumen")
+dg = df.groupby("tipo_activo").agg({"costo": "sum", "hoy": "sum", "gan": "sum"}).reset_index()
+vt_tab = pd.DataFrame(
+    {
+        "Tipo": dg["tipo_activo"].astype(str).str.upper(),
+        "Inversión": (dg["costo"] * f).apply(lambda x: fmt(x, s)),
+        "Valor": (dg["hoy"] * f).apply(lambda x: fmt(x, s)),
+        "Rend": ((dg["hoy"] / dg["costo"].replace(0, pd.NA) - 1) * 100).fillna(0).map("{:.1f}%".format),
+    }
+)
+st.dataframe(
+    pd.concat(
+        [
+            vt_tab,
+            pd.DataFrame(
+                {
+                    "Tipo": ["TOTAL"],
+                    "Inversión": [fmt(it * f, s)],
+                    "Valor": [fmt(vt * f, s)],
+                    "Rend": [f"{tir:.1f}%"],
+                }
+            ),
+        ]
+    ),
+    hide_index=True,
+    use_container_width=True,
+)
+
+g1, g2 = st.columns(2)
+g1.plotly_chart(px.pie(dg, values="hoy", names="tipo_activo", title="Tipos", hole=0.5), use_container_width=True)
+db = df.groupby("broker")["hoy"].sum().reset_index()
+g2.plotly_chart(px.bar(db, x="broker", y=db["hoy"] * f, color="broker", title="Broker"), use_container_width=True)
+
+g3, g4 = st.columns(2)
+dt = df.groupby("ticker").agg({"hoy": "sum", "gan": "sum"}).reset_index()
+g3.plotly_chart(px.pie(dt, values="hoy", names="ticker", title="Tickers", hole=0.4), use_container_width=True)
+g4.plotly_chart(
+    px.bar(
+        dt.sort_values("gan"),
+        x="ticker",
+        y=dt["gan"] * f,
+        color="gan",
+        title="Ganancia/Pérdida",
+        color_continuous_scale="RdYlGn",
+    ),
+    use_container_width=True,
+)
 
EOF
)

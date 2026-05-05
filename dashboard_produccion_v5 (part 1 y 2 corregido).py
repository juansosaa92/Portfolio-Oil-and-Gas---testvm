# ============================================================
# Dashboard Vaca Muerta — Producción + Trayectoria 3D + Mapa
# Formación Vaca Muerta · Cuenca Neuquina
# Fuente: Secretaría de Energía · Capítulo IV
#
# Para correr:
#   pip install streamlit plotly pandas numpy
#   streamlit run dashboard_produccion_v3.py
# ============================================================

import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# Directorio base del script (funciona local y en Streamlit Cloud)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Configuración de página ──────────────────────────────────
st.set_page_config(
    page_title="Vaca Muerta · Dashboard",
    page_icon="🛢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Helpers ──────────────────────────────────────────────────
def hex_to_rgba(hex_color, opacity=0.15):
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return f"rgba({r},{g},{b},{opacity})"

def make_colorscale(hex_color):
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return [
        [0,   f"rgba({int(r*0.5)},{int(g*0.5)},{int(b*0.5)},0.72)"],
        [0.5, f"rgba({int(r*0.75)},{int(g*0.75)},{int(b*0.75)},0.72)"],
        [1,   f"rgba({r},{g},{b},0.72)"]
    ]

LAYOUT_BASE = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(t=10, b=40, l=60, r=20),
    hovermode="x unified",
    height=300,
    xaxis=dict(
        tickformat="%b %Y",
        dtick="M3",
        tickangle=-30,
        gridcolor="#21262d"
    ),
    yaxis=dict(gridcolor="#21262d")
)

# ── Colores por fluido ────────────────────────────────────────
C_OIL   = "#2ecc71"   # verde
C_GAS   = "#e74c3c"   # rojo
C_AGUA  = "#3fc3ee"   # celeste
C_TOT   = "#ecf0f1"   # blanco/gris claro (total)

# ── Factores de conversión ────────────────────────────────────
BBL_PER_M3  = 6.28981    # 1 m³ = 6.28981 bbl
BOE_PER_M3G = 158.99     # 1 BOE gas = 158.99 m³ gas

# ── Columna estratigráfica ────────────────────────────────────
STRAT = [
    {"name": "Neuquén",     "top": 0,    "base": 1200, "color": "#8b6f4e", "texture": "granular"},
    {"name": "Rayoso",      "top": 1200, "base": 1800, "color": "#4a9eff", "texture": "laminar"},
    {"name": "Agrio",       "top": 1800, "base": 2500, "color": "#a0c4ff", "texture": "nodular"},
    {"name": "Quintuco",    "top": 2500, "base": 3400, "color": "#ffd700", "texture": "masivo"},
    {"name": "VM Superior", "top": 3400, "base": 4200, "color": "#3fb950", "texture": "ondulado"},
    {"name": "VM Inferior", "top": 4200, "base": 5000, "color": "#f78166", "texture": "laminado"},
    {"name": "Tordillo",    "top": 5000, "base": 5500, "color": "#d2a8ff", "texture": "cruzado"},
    {"name": "Precuyano",   "top": 5500, "base": 5868, "color": "#ff6b6b", "texture": "irregular"},
]

# ── Estilos ───────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 1.2rem; }
    .stMetric label  { font-size: 0.82rem !important; }
    div[data-testid="metric-container"] {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 10px 14px;
    }
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# CARGA Y PROCESAMIENTO DE DATOS
# Los CSV ya vienen con columnas pre-calculadas por la SecEn:
#   prod_pet(m3/mes), prod_pet(m3/d), prod_pet(bbl/d)
#   prod_gas(Mm3/mes), prod_gas(m3/d), prod_gas(BOE/d)
#   prod_agua(m3/mes), prod_agua(m3/d), prod_agua(bbl/d)
#   total_prod_fluidos(boe/d)
# ════════════════════════════════════════════════════════════
@st.cache_data
def cargar_datos():
    partes = [
        os.path.join(BASE_DIR, "prodvm_part1.csv"),
        os.path.join(BASE_DIR, "prodvm_part2.csv"),
    ]
    df = pd.concat(
        [pd.read_csv(p, low_memory=False) for p in partes],
        ignore_index=True
    )

    # Renombrar columnas con caracteres especiales para facilitar acceso
    rename_map = {
        "prod_pet(m3/mes)":        "prod_pet_m3mes",
        "prod_pet(m3/d)":          "prod_pet_m3d",
        "prod_pet(bbl/d)":         "prod_pet_bbld",
        "prod_gas(Mm3/mes)":       "prod_gas_mm3mes",
        "prod_gas(m3/d)":          "prod_gas_m3d",
        "prod_gas(BOE/d)":         "prod_gas_boed",
        "prod_agua(m3/mes)":       "prod_agua_m3mes",
        "prod_agua(m3/d)":         "prod_agua_m3d",
        "prod_agua(bbl/d)":        "prod_agua_bbld",
        "total_prod_fluidos(boe/d)": "total_boed",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Fecha cronológica
    df["fecha"] = pd.to_datetime(
        df["anio"].astype(str) + "-" + df["mes"].astype(str).str.zfill(2) + "-01"
    )

    # Ordenar cronológicamente
    df = df.sort_values(["sigla", "fecha"]).reset_index(drop=True)

    # Filtrar meses sin producción
    df = df[(df["prod_pet_m3mes"] > 0) | (df["prod_gas_mm3mes"] > 0)].copy()

    # Días por mes (para acumuladas consistentes)
    df["dias"] = df["fecha"].dt.days_in_month

    # ── Tasas diarias métricas ────────────────────────────────
    # Petróleo
    df["oil_m3d"]   = df["prod_pet_m3d"].round(2)
    df["oil_bbld"]  = df["prod_pet_bbld"].round(1)
    df["oil_m3mes"] = df["prod_pet_m3mes"].round(1)

    # Gas  (el CSV ya trae Mm³/mes; recalculamos m³/d para consistencia)
    df["gas_mm3mes"] = df["prod_gas_mm3mes"].round(4)
    df["gas_m3mes"]  = (df["prod_gas_mm3mes"] * 1000).round(1)
    df["gas_m3d"]    = df["prod_gas_m3d"].round(2)
    df["gas_mm3d"]   = (df["prod_gas_m3d"] / 1000).round(5)
    df["gas_boed"]   = df["prod_gas_boed"].round(2)

    # Agua
    df["agua_m3d"]   = df["prod_agua_m3d"].round(2)
    df["agua_bbld"]  = df["prod_agua_bbld"].round(1)
    df["agua_m3mes"] = df["prod_agua_m3mes"].round(1)

    # ── Totales diarios ───────────────────────────────────────
    # Métrico: suma de m³/d de petróleo + gas + agua
    df["total_m3d"]  = (df["oil_m3d"] + df["gas_m3d"] + df["agua_m3d"]).round(2)
    # Campo: BOE/d total (ya viene en el CSV)
    df["total_boed"] = df["total_boed"].round(1) if "total_boed" in df.columns else (
        df["oil_bbld"] + df["gas_boed"] + df["agua_bbld"]
    ).round(1)

    # ── GOR y WC ─────────────────────────────────────────────
    df["gor"] = (df["gas_m3mes"] / df["oil_m3mes"].replace(0, np.nan)).round(2)
    liq = df["oil_m3mes"] + df["agua_m3mes"]
    df["wc"]  = (df["agua_m3mes"] / liq.replace(0, np.nan) * 100).round(2)

    # ── Acumuladas por pozo ───────────────────────────────────
    # Petróleo en m³ y bbl
    df["cum_oil_m3"]   = df.groupby("sigla")["oil_m3mes"].cumsum().round(0)
    df["cum_oil_bbl"]  = (df["cum_oil_m3"] * BBL_PER_M3).round(0)
    # Gas en Mm³ y BOE
    df["cum_gas_mm3"]  = df.groupby("sigla")["gas_mm3mes"].cumsum().round(3)
    df["cum_gas_m3"]   = (df["cum_gas_mm3"] * 1000).round(0)
    df["cum_gas_boe"]  = (df["cum_gas_m3"] / BOE_PER_M3G).round(0)
    # Agua en m³ y bbl
    df["cum_agua_m3"]  = df.groupby("sigla")["agua_m3mes"].cumsum().round(0)
    df["cum_agua_bbl"] = (df["cum_agua_m3"] * BBL_PER_M3).round(0)
    # Total
    df["cum_total_m3"]  = (df["cum_oil_m3"] + df["cum_gas_m3"] + df["cum_agua_m3"]).round(0)
    df["cum_total_boe"] = (df["cum_oil_bbl"] + df["cum_gas_boe"] + df["cum_agua_bbl"]).round(0)

    return df

# ── Selector de archivo en sidebar ───────────────────────────
# (se llama luego de definir el sidebar)

# ════════════════════════════════════════════════════════════
# SIDEBAR — FILTROS
# ════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("⚙️ Filtros")
    st.markdown("---")

    # Empresa
    df_full = cargar_datos()

    empresas = sorted(df_full["empresa"].unique())
    emp_sel = st.selectbox("🏢 Empresa:", empresas)

    # Yacimiento (filtrado por empresa)
    yac_opts = sorted(df_full[df_full["empresa"] == emp_sel]["areayacimiento"].unique())
    yac_sel  = st.selectbox("📍 Yacimiento:", yac_opts)

    # Pozo (filtrado por empresa + yacimiento)
    pozo_opts = sorted(
        df_full[(df_full["empresa"] == emp_sel) &
                (df_full["areayacimiento"] == yac_sel)]["sigla"].unique()
    )
    pozo_sel = st.selectbox("📌 Pozo:", pozo_opts)

    st.markdown("---")

    # Unidades
    unidades = st.radio("📐 Unidades:", ["Métrico (m³)", "Campo (bbl / BOE)"])
    metrico  = unidades == "Métrico (m³)"

    # Escala Y
    escala_y = st.radio("📊 Escala eje Y:", ["Lineal", "Logarítmica"])

    # Período
    df_pozo_full = df_full[df_full["sigla"] == pozo_sel].copy()
    n_meses = len(df_pozo_full)
    if n_meses > 3:
        periodo = st.slider("📅 Período (meses):", min_value=3,
                            max_value=n_meses, value=n_meses, step=1)
    else:
        periodo = n_meses
        if n_meses > 0:
            st.caption(f"📅 Período: {n_meses} mes{'es' if n_meses > 1 else ''}")

    st.markdown("---")

    # Info del pozo seleccionado
    if not df_pozo_full.empty:
        row = df_pozo_full.iloc[0]
        st.markdown("**📋 Resumen del pozo**")
        st.caption(f"**Sigla:** {row['sigla']}")
        st.caption(f"**Empresa:** {row['empresa']}")
        st.caption(f"**Formación:** {row['formacion'].title()}")
        st.caption(f"**Yacimiento:** {row['areayacimiento'].title()}")
        st.caption(f"**Tipo pozo:** {row['tipopozo']}")
        st.caption(f"**Profundidad:** {row['profundidad']:,.0f} m")
        st.caption(f"**Provincia:** {row['provincia']}")
        inicio = df_pozo_full["fecha"].min().strftime("%b %Y")
        fin    = df_pozo_full["fecha"].max().strftime("%b %Y")
        st.caption(f"**Período:** {inicio} – {fin}")
        st.caption(f"**Coord. X:** {row['coordenadax']:.5f}")
        st.caption(f"**Coord. Y:** {row['coordenaday']:.5f}")

# ── Filtrar al pozo y período seleccionado ────────────────────
df = df_pozo_full.head(periodo).copy()

# ── Detectar cambios de sistema de extracción ─────────────────
cambios_ext = []
if len(df) > 1:
    for i in range(1, len(df)):
        prev = df.iloc[i-1]["tipoextraccion"]
        curr = df.iloc[i]["tipoextraccion"]
        if prev != curr:
            cambios_ext.append({
                "fecha": df.iloc[i]["fecha"],
                "de": prev,
                "a": curr
            })

def agregar_cambios_ext(fig):
    for c in cambios_ext:
        fig.add_vline(
            x=c["fecha"].timestamp() * 1000,
            line=dict(color="#f0e68c", width=1.5, dash="dash"),
            annotation_text="⚙",
            annotation_position="top",
            annotation=dict(
                font=dict(size=14, color="#f0e68c"),
                hovertext=f"Cambio extracción: {c['de']} → {c['a']}",
                showarrow=False
            )
        )
    return fig

# ── Selector de columnas según unidades (COMPLETO) ─────────────
def cols_unidades(fluido):
    """
    Devuelve (col_tasa, col_acum, label_tasa, label_acum, fmt_tasa, fmt_acum)
    según fluido y unidades seleccionadas. Todas las columnas cambian coherentemente.
    """
    if fluido == "oil":
        if metrico:
            return ("oil_m3d",   "cum_oil_m3",  "m³/d",   "m³",    ",.2f", ",.0f")
        else:
            return ("oil_bbld",  "cum_oil_bbl", "bbl/d",  "bbl",   ",.1f", ",.0f")
    elif fluido == "gas":
        if metrico:
            return ("gas_mm3d",  "cum_gas_mm3", "Mm³/d",  "Mm³",   ",.4f", ",.3f")
        else:
            return ("gas_boed",  "cum_gas_boe", "BOE/d",  "BOE",   ",.1f", ",.0f")
    elif fluido == "agua":
        if metrico:
            return ("agua_m3d",  "cum_agua_m3", "m³/d",   "m³",    ",.2f", ",.0f")
        else:
            return ("agua_bbld", "cum_agua_bbl","bbl/d",  "bbl",   ",.1f", ",.0f")
    else:  # total
        if metrico:
            return ("total_m3d", "cum_total_m3","m³/d eq.","m³",   ",.2f", ",.0f")
        else:
            return ("total_boed","cum_total_boe","BOE/d",  "BOE",  ",.1f", ",.0f")

def fig_layout(title_y, height=300):
    layout = dict(LAYOUT_BASE)
    layout["height"] = height
    layout["yaxis"] = dict(
        title=title_y,
        gridcolor="#21262d",
        type="log" if escala_y == "Logarítmica" else "linear"
    )
    return layout

def fig_layout_fixed_range(title_y, y_range, height=300):
    """Layout con rango Y fijo (para WC %)."""
    layout = dict(LAYOUT_BASE)
    layout["height"] = height
    layout["yaxis"] = dict(title=title_y, gridcolor="#21262d", range=y_range)
    return layout

# ── Helper para grafico de línea estándar ────────────────────
def scatter_fluido(fig, x, y, color, u, fmt, name, fill=True):
    fig.add_trace(go.Scatter(
        x=x, y=y,
        name=name, mode="lines+markers",
        fill="tozeroy" if fill else "none",
        fillcolor=hex_to_rgba(color, 0.13),
        line=dict(color=color, width=2.5),
        marker=dict(size=5),
        hovertemplate=f"<b>%{{x|%b %Y}}</b><br>%{{y:{fmt}}} {u}<extra></extra>"
    ))
    return fig

# ════════════════════════════════════════════════════════════
# TÍTULO + TABS
# ════════════════════════════════════════════════════════════
st.title("🛢 Dashboard Vaca Muerta — Cuenca Neuquina")
st.markdown(
    f"**{pozo_sel}** · {df_pozo_full.iloc[0]['areayacimiento'].title()} · "
    f"{df_pozo_full.iloc[0]['empresa']} · "
    f"*Datos reales — Secretaría de Energía · Capítulo IV*"
)
st.markdown("---")

tab_prod, tab_3d, tab_mapa = st.tabs(["📊 Producción", "🌍 Trayectoria 3D", "🗺️ Mapa"])

# ════════════════════════════════════════════════════════════
# TAB 1: PRODUCCIÓN
# ════════════════════════════════════════════════════════════
with tab_prod:

    # ── KPIs ─────────────────────────────────────────────────
    st.subheader("Indicadores del Pozo")

    # Tasas actuales y pico
    oil_act   = df["oil_m3d"].iloc[-1]   if metrico else df["oil_bbld"].iloc[-1]
    oil_pico  = df["oil_m3d"].max()      if metrico else df["oil_bbld"].max()
    gas_act   = df["gas_mm3d"].iloc[-1]  if metrico else df["gas_boed"].iloc[-1]
    gas_pico  = df["gas_mm3d"].max()     if metrico else df["gas_boed"].max()
    agua_act  = df["agua_m3d"].iloc[-1]  if metrico else df["agua_bbld"].iloc[-1]
    agua_pico = df["agua_m3d"].max()     if metrico else df["agua_bbld"].max()

    # Acumuladas según unidades
    cum_oil   = df["cum_oil_m3"].iloc[-1]   if metrico else df["cum_oil_bbl"].iloc[-1]
    cum_gas   = df["cum_gas_mm3"].iloc[-1]  if metrico else df["cum_gas_boe"].iloc[-1]
    cum_agua  = df["cum_agua_m3"].iloc[-1]  if metrico else df["cum_agua_bbl"].iloc[-1]

    wc_act    = df["wc"].iloc[-1]
    gor_act   = df["gor"].iloc[-1]
    delta_oil = round((oil_act - oil_pico) / oil_pico * 100, 1) if oil_pico else 0

    u_oil  = "m³/d"  if metrico else "bbl/d"
    u_gas  = "Mm³/d" if metrico else "BOE/d"
    u_agua = "m³/d"  if metrico else "bbl/d"

    u_cum_oil  = "m³"  if metrico else "bbl"
    u_cum_gas  = "Mm³" if metrico else "BOE"
    u_cum_agua = "m³"  if metrico else "bbl"

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        st.metric(f"🛢 Petróleo actual", f"{oil_act:,.1f} {u_oil}",
                  delta=f"{delta_oil}% vs pico")
        st.caption(f"Pico: {oil_pico:,.1f} {u_oil}")
    with k2:
        st.metric(f"🔥 Gas actual", f"{gas_act:,.4f} {u_gas}")
        st.caption(f"Pico: {gas_pico:,.4f} {u_gas}")
    with k3:
        st.metric(f"💧 Agua actual", f"{agua_act:,.1f} {u_agua}")
        st.caption(f"WC: {wc_act:.1f}%")
    with k4:
        st.metric(f"🛢 Acum. Petróleo", f"{cum_oil:,.0f} {u_cum_oil}")
        st.caption(f"Pico: {oil_pico:,.1f} {u_oil}")
    with k5:
        st.metric(f"🔥 Acum. Gas", f"{cum_gas:,.3f} {u_cum_gas}")
        st.caption(f"GOR: {gor_act:,.1f} m³/m³")
    with k6:
        st.metric(f"💧 Acum. Agua", f"{cum_agua:,.0f} {u_cum_agua}")
        st.caption(f"WC actual: {wc_act:.1f}%")

    st.markdown("---")

    # ── Obtenemos columnas para cada fluido ──────────────────
    oil_col,  oil_cum,  oil_u,  oil_ucum,  oil_fmt,  oil_fmtc  = cols_unidades("oil")
    gas_col,  gas_cum,  gas_u,  gas_ucum,  gas_fmt,  gas_fmtc  = cols_unidades("gas")
    agua_col, agua_cum, agua_u, agua_ucum, agua_fmt, agua_fmtc = cols_unidades("agua")
    tot_col,  tot_cum,  tot_u,  tot_ucum,  tot_fmt,  tot_fmtc  = cols_unidades("total")

    # ── Fila 1: Petróleo prod | Petróleo acum ────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"🛢 Prod. Petróleo ({oil_u})")
        fig = go.Figure()
        scatter_fluido(fig, df["fecha"], df[oil_col], C_OIL, oil_u, oil_fmt, "Petróleo")
        agregar_cambios_ext(fig)
        fig.update_layout(**fig_layout(oil_u))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader(f"🛢 Acum. Petróleo ({oil_ucum})")
        fig = go.Figure()
        scatter_fluido(fig, df["fecha"], df[oil_cum], C_OIL, oil_ucum, oil_fmtc, "Acum. Petróleo")
        agregar_cambios_ext(fig)
        fig.update_layout(**fig_layout(oil_ucum))
        st.plotly_chart(fig, use_container_width=True)

    # ── Fila 2: Gas prod | Gas acum ──────────────────────────
    col3, col4 = st.columns(2)

    with col3:
        st.subheader(f"🔥 Prod. Gas ({gas_u})")
        fig = go.Figure()
        scatter_fluido(fig, df["fecha"], df[gas_col], C_GAS, gas_u, gas_fmt, "Gas")
        agregar_cambios_ext(fig)
        fig.update_layout(**fig_layout(gas_u))
        st.plotly_chart(fig, use_container_width=True)

    with col4:
        st.subheader(f"🔥 Acum. Gas ({gas_ucum})")
        fig = go.Figure()
        scatter_fluido(fig, df["fecha"], df[gas_cum], C_GAS, gas_ucum, gas_fmtc, "Acum. Gas")
        agregar_cambios_ext(fig)
        fig.update_layout(**fig_layout(gas_ucum))
        st.plotly_chart(fig, use_container_width=True)

    # ── Fila 3: Agua prod | Agua acum ────────────────────────
    col5, col6 = st.columns(2)

    with col5:
        st.subheader(f"💧 Prod. Agua ({agua_u})")
        fig = go.Figure()
        scatter_fluido(fig, df["fecha"], df[agua_col], C_AGUA, agua_u, agua_fmt, "Agua")
        agregar_cambios_ext(fig)
        fig.update_layout(**fig_layout(agua_u))
        st.plotly_chart(fig, use_container_width=True)

    with col6:
        st.subheader(f"💧 Acum. Agua ({agua_ucum})")
        fig = go.Figure()
        scatter_fluido(fig, df["fecha"], df[agua_cum], C_AGUA, agua_ucum, agua_fmtc, "Acum. Agua")
        agregar_cambios_ext(fig)
        fig.update_layout(**fig_layout(agua_ucum))
        st.plotly_chart(fig, use_container_width=True)

    # ── Fila 4: Producción total | Acum. total ────────────────
    col9, col10 = st.columns(2)

    with col9:
        st.subheader(f"🛢 Prod. Total ({tot_u})")
        fig = go.Figure()
        scatter_fluido(fig, df["fecha"], df[tot_col], C_TOT, tot_u, tot_fmt, "Total")
        agregar_cambios_ext(fig)
        lay = dict(LAYOUT_BASE)
        lay["height"] = 300
        lay["yaxis"] = dict(title=tot_u, gridcolor="#21262d",
                            type="log" if escala_y == "Logarítmica" else "linear")
        fig.update_layout(**lay)
        st.plotly_chart(fig, use_container_width=True)

    with col10:
        st.subheader(f"🛢 Acum. Total ({tot_ucum})")
        fig = go.Figure()
        scatter_fluido(fig, df["fecha"], df[tot_cum], C_TOT, tot_ucum, tot_fmtc, "Acum. Total")
        agregar_cambios_ext(fig)
        lay = dict(LAYOUT_BASE)
        lay["height"] = 300
        lay["yaxis"] = dict(title=tot_ucum, gridcolor="#21262d")
        fig.update_layout(**lay)
        st.plotly_chart(fig, use_container_width=True)

    # ── Fila 5: GOR | WC ─────────────────────────────────────
    col7, col8 = st.columns(2)

    with col7:
        st.subheader("⚗️ GOR (m³/m³)")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["fecha"], y=df["gor"],
            name="GOR", mode="lines+markers",
            line=dict(color="#f39c12", width=2.5),
            marker=dict(size=5),
            hovertemplate="<b>%{x|%b %Y}</b><br>GOR: %{y:,.2f} m³/m³<extra></extra>"
        ))
        agregar_cambios_ext(fig)
        fig.update_layout(**fig_layout("m³/m³"))
        st.plotly_chart(fig, use_container_width=True)

    with col8:
        st.subheader("💧 Corte de Agua — WC (%)")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["fecha"], y=df["wc"],
            name="WC%", mode="lines+markers",
            fill="tozeroy", fillcolor=hex_to_rgba(C_AGUA, 0.13),
            line=dict(color=C_AGUA, width=2.5),
            marker=dict(size=5),
            hovertemplate="<b>%{x|%b %Y}</b><br>WC: %{y:.2f}%<extra></extra>"
        ))
        agregar_cambios_ext(fig)
        fig.update_layout(**fig_layout_fixed_range("%", [0, 100]))
        st.plotly_chart(fig, use_container_width=True)

    # ── Tabla de datos ────────────────────────────────────────
    st.markdown("---")
    with st.expander("📋 Ver tabla de datos completa"):
        cols_tabla = [
            "fecha", "empresa", "sigla",
            "oil_m3d", "oil_bbld",
            "gas_mm3d", "gas_boed",
            "agua_m3d", "agua_bbld",
            "total_m3d", "total_boed",
            "gor", "wc",
            "cum_oil_m3", "cum_oil_bbl",
            "cum_gas_mm3", "cum_gas_boe",
            "cum_agua_m3", "cum_agua_bbl",
            "cum_total_m3", "cum_total_boe",
            "tipoextraccion", "formacion", "areayacimiento",
            "profundidad", "coordenadax", "coordenaday"
        ]
        cols_tabla = [c for c in cols_tabla if c in df.columns]
        df_t = df[cols_tabla].copy()
        df_t["fecha"] = df_t["fecha"].dt.strftime("%b %Y")
        df_t.columns = [c.replace("_", " ").title() for c in df_t.columns]
        st.dataframe(df_t, use_container_width=True, hide_index=True)
        csv = df_t.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar CSV procesado",
            csv, f"{pozo_sel}_produccion.csv", "text/csv"
        )

# ════════════════════════════════════════════════════════════
# TAB 2: TRAYECTORIA 3D
# ════════════════════════════════════════════════════════════
with tab_3d:

    col_3d, col_info = st.columns([3, 1])

    with col_info:
        st.subheader("🪨 Columna Estratigráfica")
        for s in STRAT:
            is_target = s["name"] == "VM Inferior"
            label = f"🎯 **{s['name']}**" if is_target else f"**{s['name']}**"
            st.markdown(
                f"<div style='border-left:3px solid {s['color']};padding:6px 10px;"
                f"margin-bottom:6px;background:{'#f7816611' if is_target else '#ffffff08'};"
                f"border-radius:0 6px 6px 0'>"
                f"{label}<br>"
                f"<span style='font-size:0.75rem;color:#8b949e'>"
                f"{s['top']:,}–{s['base']:,} m TVD</span>"
                f"</div>",
                unsafe_allow_html=True
            )
        st.markdown("---")
        st.markdown("**Parámetros del modelo**")
        st.caption("📐 Azimut: N 85° E")
        st.caption("↗ Buzamiento: ~2° E")
        st.caption("⬇ KOP estimado: 1.500 m TVD")
        st.caption("🎯 Target: ~5.100 m TVD")
        st.caption("📏 Rama horiz. est.: 2.500 m")
        st.caption(f"📍 {df_pozo_full.iloc[0]['areayacimiento'].title()}, Neuquén")
        st.caption(f"🔢 ID Pozo: {df_pozo_full.iloc[0]['idpozo']}")

    with col_3d:
        st.subheader("Vista 3D — Trayectoria + Estratigrafía")

        @st.cache_data
        def generar_trayectoria():
            dip_rate = np.tan(2 * np.pi / 180)
            az       = 85 * np.pi / 180
            kickoff  = 1500
            tvd_tgt  = 5100
            horz_len = 2500
            xs, ys, zs = [], [], []
            for i in range(41):
                xs.append(0.0); ys.append(0.0); zs.append(-(kickoff/40)*i)
            build_len = (tvd_tgt - kickoff) * 1.62
            tvd_c, e_c, n_c = kickoff, 0.0, 0.0
            for i in range(1, 81):
                inc   = (i/80) * np.pi/2
                dl    = build_len/80
                tvd_c = min(tvd_c + dl*np.cos(inc), tvd_tgt)
                e_c  += dl*np.sin(inc)*np.sin(az)
                n_c  += dl*np.sin(inc)*np.cos(az)
                xs.append(e_c); ys.append(n_c); zs.append(-tvd_c)
            lx, ly, lz = xs[-1], ys[-1], zs[-1]
            for i in range(1, 81):
                d = (horz_len/80)*i
                xs.append(lx + d*np.sin(az))
                ys.append(ly + d*np.cos(az))
                zs.append(lz - d*np.sin(az)*dip_rate)
            return xs, ys, zs

        @st.cache_data
        def generar_superficies():
            xs_t, ys_t, _ = generar_trayectoria()
            NX, NY = 25, 18
            xg = np.linspace(-300, max(xs_t)+300, NX)
            yg = np.linspace(-300, max(abs(y) for y in ys_t)+300, NY)
            dip = np.tan(2*np.pi/180)
            surfaces = []
            for s in STRAT:
                Z = np.array([[-(s["top"]+x*dip) for x in xg] for _ in yg])
                C = np.zeros((NY, NX))
                t = s["texture"]
                for j, y in enumerate(yg):
                    for i, x in enumerate(xg):
                        if t=="granular":   C[j,i]=np.sin(x*0.08)*np.cos(y*0.08)+np.sin(x*0.19+1.3)*0.5
                        elif t=="laminar":  C[j,i]=np.sin(y*0.35)+np.sin(y*0.7)*0.3
                        elif t=="nodular":  C[j,i]=np.sin(x*0.05)*np.sin(y*0.08)+np.cos(x*0.12)*0.4
                        elif t=="masivo":   C[j,i]=(x/(max(xs_t)+600))*0.3+np.sin(x*0.01+y*0.01)*0.1
                        elif t=="ondulado": C[j,i]=np.sin(x*0.025+y*0.015)+np.cos(x*0.012)*0.5
                        elif t=="laminado": C[j,i]=np.sin(y*0.5)+np.sin(y*1.1)*0.4+np.sin(x*0.03)*0.2
                        elif t=="cruzado":  C[j,i]=np.sin((x+y)*0.06)+np.sin((x-y)*0.04)*0.6
                        else:               C[j,i]=np.sin(x*0.1)*np.cos(y*0.13)+np.sin(x*0.07+y*0.09)*0.7
                surfaces.append({"name":s["name"],"color":s["color"],
                                 "top":s["top"],"base":s["base"],
                                 "xg":xg.tolist(),"yg":yg.tolist(),
                                 "Z":Z.tolist(),"C":C.tolist(),
                                 "is_target":s["name"]=="VM Inferior"})
            return surfaces

        traj     = generar_trayectoria()
        surfaces = generar_superficies()
        xs, ys, zs = traj

        fig3d = go.Figure()

        for s in surfaces:
            fig3d.add_trace(go.Surface(
                x=s["xg"], y=s["yg"], z=s["Z"],
                surfacecolor=s["C"],
                colorscale=make_colorscale(s["color"]),
                opacity=0.55 if s["is_target"] else 0.22,
                showscale=False, name=s["name"], showlegend=True,
                hovertemplate=(f"<b>{s['name']}</b><br>"
                               "E: %{x:.0f} m<br>N: %{y:.0f} m<br>"
                               "TVD: %{z:.0f} m<extra></extra>"),
                lighting=dict(ambient=0.9, diffuse=0.3)
            ))

        fig3d.add_trace(go.Scatter3d(
            x=xs, y=ys, z=zs, name=pozo_sel, mode="lines",
            line=dict(color=C_OIL, width=7),
            hovertemplate=(f"<b>{pozo_sel}</b><br>"
                           "E: %{x:.0f} m<br>N: %{y:.0f} m<br>"
                           "TVD: %{z:.0f} m<extra></extra>")
        ))

        fig3d.add_trace(go.Scatter3d(
            x=[0,0], y=[0,0], z=[0,-1500], mode="lines",
            line=dict(color=C_OIL, width=1, dash="dot"),
            showlegend=False, hoverinfo="skip"
        ))

        fig3d.add_trace(go.Scatter3d(
            x=[0], y=[0], z=[0],
            mode="markers+text", text=[pozo_sel],
            textposition="top center",
            textfont=dict(color="#e6edf3", size=10),
            marker=dict(size=7, color=C_OIL, symbol="diamond"),
            name="Boca de pozo",
            hovertemplate=f"<b>{pozo_sel}</b><br>Superficie<extra></extra>"
        ))

        fig3d.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#8b949e", size=11),
            margin=dict(t=10,b=10,l=0,r=0), height=600,
            scene=dict(
                bgcolor="#0d1117",
                xaxis=dict(title="Este (m)",  gridcolor="#21262d", linecolor="#30363d"),
                yaxis=dict(title="Norte (m)", gridcolor="#21262d", linecolor="#30363d"),
                zaxis=dict(title="TVD (m)",   gridcolor="#21262d", linecolor="#30363d"),
                camera=dict(eye=dict(x=-1.6, y=-1.4, z=0.8)),
                aspectmode="manual", aspectratio=dict(x=2.2, y=0.8, z=1)
            ),
            legend=dict(bgcolor="#161b22", bordercolor="#30363d",
                        borderwidth=1, font=dict(size=10))
        )
        st.plotly_chart(fig3d, use_container_width=True)

        with st.expander("📐 Ver perfil vertical (Este vs TVD)"):
            dip = np.tan(2*np.pi/180)
            fig2d = go.Figure()
            xr = [-300, max(xs)+300]
            for s in surfaces:
                tl = -(s["top"] +xr[0]*dip); tr = -(s["top"] +xr[1]*dip)
                bl = -(s["base"]+xr[0]*dip); br = -(s["base"]+xr[1]*dip)
                is_t = s["is_target"]
                fig2d.add_trace(go.Scatter(
                    x=[xr[0],xr[1],xr[1],xr[0],xr[0]],
                    y=[tl,tr,br,bl,tl], fill="toself",
                    fillcolor=hex_to_rgba(s["color"], 0.18 if is_t else 0.07),
                    line=dict(color=s["color"],
                              width=1.5 if is_t else 0.5,
                              dash="solid" if is_t else "dot"),
                    showlegend=False,
                    hovertemplate=f"<b>{s['name']}</b><extra></extra>"
                ))
                x_l = xr[0]+150; y_m = -(s["top"]+s["base"])/2 - x_l*dip
                fig2d.add_annotation(x=x_l, y=y_m, text=s["name"],
                    showarrow=False, font=dict(color=s["color"], size=9), xanchor="left")
            fig2d.add_trace(go.Scatter(
                x=xs, y=zs, name=pozo_sel, mode="lines",
                line=dict(color=C_OIL, width=2.5),
                hovertemplate=(f"<b>{pozo_sel}</b><br>"
                               "E: %{x:.0f} m<br>TVD: %{y:.0f} m<extra></extra>")
            ))
            fig2d.update_layout(
                template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)", height=400,
                margin=dict(t=10,b=50,l=65,r=20),
                xaxis=dict(title="Desplazamiento Este (m)", gridcolor="#21262d", zeroline=False),
                yaxis=dict(title="TVD (m)", gridcolor="#21262d", zeroline=False),
                hovermode="closest"
            )
            st.plotly_chart(fig2d, use_container_width=True)

# ════════════════════════════════════════════════════════════
# TAB 3: MAPA 2D
# ════════════════════════════════════════════════════════════
with tab_mapa:
    st.subheader("🗺️ Ubicación del Pozo — Mapa Satelital")

    row = df_pozo_full.iloc[0]
    lat = row["coordenaday"]   # Y = latitud
    lon = row["coordenadax"]   # X = longitud

    # Todos los pozos del CSV para contexto
    df_pozos_mapa = df_full.drop_duplicates("sigla")[
        ["sigla","empresa","areayacimiento","formacion","profundidad",
         "coordenadax","coordenaday"]
    ].copy()
    df_pozos_mapa = df_pozos_mapa.rename(
        columns={"coordenadax": "lon", "coordenaday": "lat"}
    )
    df_pozos_mapa["selected"] = df_pozos_mapa["sigla"] == pozo_sel
    df_pozos_mapa["color"]    = df_pozos_mapa["selected"].map(
        {True: "#2ecc71", False: "#58a6ff"}
    )
    df_pozos_mapa["size"]     = df_pozos_mapa["selected"].map({True: 14, False: 8})

    fig_mapa = go.Figure()

    # Pozos de contexto
    otros = df_pozos_mapa[~df_pozos_mapa["selected"]]
    if not otros.empty:
        fig_mapa.add_trace(go.Scattermap(
            lat=otros["lat"], lon=otros["lon"],
            mode="markers",
            marker=dict(size=8, color="#58a6ff", opacity=0.6),
            text=otros["sigla"],
            customdata=otros[["empresa","areayacimiento","profundidad"]].values,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Empresa: %{customdata[0]}<br>"
                "Yacimiento: %{customdata[1]}<br>"
                "Prof.: %{customdata[2]:,.0f} m"
                "<extra></extra>"
            ),
            name="Otros pozos"
        ))

    # Pozo seleccionado
    sel = df_pozos_mapa[df_pozos_mapa["selected"]]
    fig_mapa.add_trace(go.Scattermap(
        lat=sel["lat"], lon=sel["lon"],
        mode="markers+text",
        marker=dict(size=16, color=C_OIL, opacity=1.0),
        text=sel["sigla"],
        textposition="top right",
        textfont=dict(color=C_OIL, size=11),
        customdata=sel[["empresa","areayacimiento","profundidad"]].values,
        hovertemplate=(
            "<b>%{text}</b> ✅<br>"
            "Empresa: %{customdata[0]}<br>"
            "Yacimiento: %{customdata[1]}<br>"
            "Prof.: %{customdata[2]:,.0f} m"
            "<extra></extra>"
        ),
        name=pozo_sel
    ))

    fig_mapa.update_layout(
        map=dict(
            style="satellite-streets",
            center=dict(lat=lat, lon=lon),
            zoom=11
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=0, b=0, l=0, r=0),
        height=600,
        legend=dict(bgcolor="#161b22", bordercolor="#30363d",
                    borderwidth=1, font=dict(color="#e6edf3", size=11))
    )

    st.plotly_chart(fig_mapa, use_container_width=True)

    st.caption(
        f"📍 **{pozo_sel}** · Lat: {lat:.5f}° · Lon: {lon:.5f}° · "
        f"Yacimiento: {row['areayacimiento'].title()} · "
        f"Formación: {row['formacion'].title()}"
    )

# ── Footer ────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Dashboard · Datos reales Capítulo IV · Secretaría de Energía Argentina · "
    "Desarrollado con Streamlit + Plotly · Cuenca Neuquina"
)

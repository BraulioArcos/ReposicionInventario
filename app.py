from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from config import SEDES
from reposicion import (
    calcular_ranking,
    calcular_reposicion,
    calcular_redistribucion,
    fecha_hoy,
)


ROOT = Path(__file__).parent
EXAMPLE_CSV = ROOT / "datos_ejemplo" / "ventas_ejemplo.csv"
REQUIRED_COLUMNS = {
    "producto",
    "categoria",
    "sede",
    "fecha",
    "cantidad_vendida",
    "stock",
}


def mostrar_estado(estado):
    iconos = {
        "Crítico": "🔴 Crítico",
        "Atención": "🟠 Atención",
        "Normal": "🟢 Normal",
        "Sobrestock": "🟣 Sobrestock",
        "Sin rotación": "⚪ Sin rotación",
    }
    return iconos.get(estado, estado)


st.set_page_config(page_title="Reposición e inventario", page_icon="📦", layout="wide")
st.title("Reposición e inventario")
st.caption("Prototipo local para revisar reposición diaria con exportaciones CSV.")

uploaded_file = st.sidebar.file_uploader("Cargar exportación CSV", type=["csv"])
if uploaded_file:
    data = pd.read_csv(uploaded_file)
    source_label = uploaded_file.name
else:
    if not EXAMPLE_CSV.is_file():
        st.error(f"No se encontró el CSV de ejemplo: {EXAMPLE_CSV}")
        st.stop()
    data = pd.read_csv(EXAMPLE_CSV)
    source_label = "ventas_ejemplo.csv"

missing_columns = REQUIRED_COLUMNS.difference(data.columns)
if missing_columns:
    st.error(
        "Al archivo le faltan columnas requeridas: "
        + ", ".join(sorted(missing_columns))
    )
    st.stop()

data["fecha"] = pd.to_datetime(data["fecha"], errors="coerce")
for column in ("cantidad_vendida", "stock"):
    data[column] = pd.to_numeric(data[column], errors="coerce")
if "stock_almacen" in data.columns:
    data["stock_almacen"] = pd.to_numeric(data["stock_almacen"], errors="coerce")
else:
    st.sidebar.warning(
        "Sin stock_almacen no se sabe si hay unidades disponibles para reponer."
    )

invalid_rows = data[list(REQUIRED_COLUMNS)].isna().any(axis=1)
if invalid_rows.any():
    st.warning(
        f"Se omitieron {int(invalid_rows.sum())} filas con fechas o valores "
        "numéricos inválidos."
    )
    data = data.loc[~invalid_rows].copy()
if data.empty:
    st.error("No hay filas válidas para mostrar.")
    st.stop()

dias_objetivo = st.sidebar.slider(
    "Días de cobertura objetivo", min_value=7, max_value=45, value=7
)
categorias = sorted(data["categoria"].dropna().unique())
sedes_disponibles = [sede for sede in SEDES if sede in set(data["sede"].dropna())]
if not sedes_disponibles:
    sedes_disponibles = sorted(data["sede"].dropna().unique())

selected_categories = st.sidebar.multiselect(
    "Categorías", categorias, default=categorias
)
selected_locations = st.sidebar.multiselect(
    "Sedes", sedes_disponibles, default=sedes_disponibles
)

st.caption(f"Fuente: {source_label}")
resultado = calcular_reposicion(data, dias_objetivo=dias_objetivo)
resultado = resultado[
    resultado["Categoría"].isin(selected_categories)
    & resultado["Sede"].isin(selected_locations)
].copy()

tab_reposicion, tab_ranking, tab_redistribucion = st.tabs(
    ["Reposición de hoy", "Más vendidos", "Redistribución"]
)

with tab_reposicion:
    criticos = int((resultado["Estado"] == "Crítico").sum())
    atencion = int((resultado["Estado"] == "Atención").sum())
    unidades = int(resultado["A reponer"].sum())

    columna1, columna2, columna3 = st.columns(3)
    columna1.metric("Críticos", f"{criticos:,}")
    columna2.metric("En atención", f"{atencion:,}")
    columna3.metric("Unidades a reponer hoy", f"{unidades:,}")

    solo_alertas = st.checkbox("Solo alertas", value=True)
    tabla = resultado.copy()
    if solo_alertas:
        tabla = tabla[
            tabla["Estado"].isin(["Crítico", "Atención", "Sin rotación"])
        ]

    urgencia = {
        "Crítico": 0,
        "Atención": 1,
        "Sin rotación": 2,
        "Normal": 3,
        "Sobrestock": 4,
    }
    tabla["_urgencia"] = tabla["Estado"].map(urgencia)
    tabla = tabla.sort_values(
        ["_urgencia", "Cobertura (días)", "Producto", "Sede"],
        na_position="last",
    ).drop(columns="_urgencia")
    tabla = tabla.assign(
        Estado=tabla["Estado"].map(mostrar_estado)
    )

    st.dataframe(
        tabla,
        width="stretch",
        hide_index=True,
        column_config={
            "Cobertura (días)": st.column_config.NumberColumn(format="%.1f"),
            "Venta/día (30d)": st.column_config.NumberColumn(format="%.2f"),
            "Venta/día (7d)": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    hoy = fecha_hoy(data).date().isoformat()
    descarga = tabla.copy()
    descarga = descarga.sort_values(["Sede", "Producto"])
    csv = descarga.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Descargar lista del día",
        data=csv,
        file_name=f"reposicion_{hoy}.csv",
        mime="text/csv",
    )

with tab_ranking:
    st.caption("Ventas acumuladas en los últimos 30 días.")
    nivel = st.selectbox("Agrupar por", ["Producto", "Categoría", "Sede"])
    ranking = calcular_ranking(data, nivel=nivel, dias=30)
    figura = go.Figure(
        go.Bar(
            x=ranking["Unidades vendidas"],
            y=ranking[nivel],
            orientation="h",
            text=ranking["Unidades vendidas"],
            textposition="outside",
            cliponaxis=False,
        )
    )
    figura.update_layout(
        height=max(420, 18 * len(ranking)),
        margin={"l": 180, "r": 60, "t": 20, "b": 40},
        yaxis={"autorange": "reversed"},
        xaxis_title="Unidades vendidas",
        yaxis_title=nivel,
    )
    st.plotly_chart(figura, width="stretch")

with tab_redistribucion:
    st.info("Las sugerencias de redistribución se calcularán aquí.")

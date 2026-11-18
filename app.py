from pathlib import Path
from math import ceil

import pandas as pd
import streamlit as st

from config import SEDES


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


st.set_page_config(page_title="Reposición e inventario", page_icon="📦", layout="wide")
st.title("Reposición e inventario")
st.caption(
    "Prototipo local para explorar ventas e inventario. "
    "Los datos de ejemplo son simulados."
)

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

min_date = data["fecha"].min().date()
max_date = data["fecha"].max().date()
date_range = st.sidebar.date_input(
    "Periodo",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)
if not isinstance(date_range, tuple) or len(date_range) != 2:
    st.info("Selecciona una fecha de inicio y una fecha de fin.")
    st.stop()
start_date, end_date = date_range
coverage_days = st.sidebar.slider(
    "Días de cobertura objetivo", min_value=7, max_value=45, value=14
)

categories = sorted(data["categoria"].dropna().unique())
selected_categories = st.sidebar.multiselect(
    "Categorías", categories, default=categories
)
locations = SEDES
selected_locations = st.sidebar.multiselect("Sedes", locations, default=locations)

filtered = data.loc[
    data["fecha"].dt.date.between(start_date, end_date)
    & data["categoria"].isin(selected_categories)
    & data["sede"].isin(selected_locations)
].copy()

st.caption(f"Fuente: {source_label}")
if filtered.empty:
    st.info("No hay datos para los filtros seleccionados.")
    st.stop()

latest_stock = (
    filtered.sort_values("fecha")
    .drop_duplicates(["producto", "sede"], keep="last")
)
units_sold = int(filtered["cantidad_vendida"].sum())
total_stock = int(latest_stock["stock"].sum())
low_stock_count = int((latest_stock["stock"] <= 5).sum())

metric1, metric2, metric3, metric4 = st.columns(4)
metric1.metric("Unidades vendidas", f"{units_sold:,}")
metric2.metric("Stock al cierre", f"{total_stock:,}")
metric3.metric("Productos", f"{filtered['producto'].nunique():,}")
metric4.metric("Producto/sede con stock ≤ 5", f"{low_stock_count:,}")

sales_by_day = (
    filtered.groupby("fecha", as_index=False)["cantidad_vendida"].sum()
    .set_index("fecha")
    .rename(columns={"cantidad_vendida": "Unidades"})
)
st.subheader("Ventas durante el periodo")
st.line_chart(sales_by_day)

st.subheader("Sugerencia de reposición")
st.caption(
    f"Estimación simple: promedio de ventas diarias del periodo × "
    f"{coverage_days} días de cobertura, menos el último stock registrado. "
    "No considera tiempos de entrega ni pedidos en tránsito."
)
period_days = max((end_date - start_date).days + 1, 1)
recommendations = (
    filtered.groupby(["categoria", "sede"], as_index=False)
    .agg(unidades_vendidas=("cantidad_vendida", "sum"))
    .merge(
        latest_stock.groupby(["categoria", "sede"], as_index=False)["stock"]
        .sum(),
        on=["categoria", "sede"],
        how="left",
    )
)
recommendations["promedio_diario"] = (
    recommendations["unidades_vendidas"] / period_days
)
recommendations["reponer"] = (
    recommendations["promedio_diario"] * coverage_days
    - recommendations["stock"]
).clip(lower=0).apply(ceil)
recommendations = recommendations.sort_values(
    ["reponer", "promedio_diario"], ascending=False
)
st.dataframe(
    recommendations.rename(
        columns={
            "categoria": "Categoría",
            "sede": "Sede",
            "unidades_vendidas": "Unidades vendidas",
            "stock": "Stock actual",
            "promedio_diario": "Promedio diario",
            "reponer": "Sugerencia de reposición",
        }
    ),
    width="stretch",
    hide_index=True,
)

st.subheader("Ventas por categoría")
sales_by_category = (
    filtered.groupby("categoria")["cantidad_vendida"]
    .sum()
    .sort_values(ascending=False)
)
st.bar_chart(sales_by_category)

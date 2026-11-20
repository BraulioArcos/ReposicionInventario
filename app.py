from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import SEDES
from importar_reportes import cargar_reportes_excel
from reposicion import (
    calcular_ranking,
    calcular_reposicion,
    calcular_resumen_empresa,
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
st.caption("La venta por tienda es estimada según el surtido; la venta empresa es exacta.")

fuente = st.sidebar.radio(
    "Fuente de datos",
    ["CSV normalizado", "Reportes Excel"],
)
diagnostico = None
if fuente == "Reportes Excel":
    archivo_productos = st.sidebar.file_uploader(
        "ReporteProductos.xlsx", type=["xlsx"], key="reporte_productos"
    )
    archivo_ventas = st.sidebar.file_uploader(
        "ReporteVentas1.xlsx", type=["xlsx"], key="reporte_ventas"
    )
    if not archivo_productos or not archivo_ventas:
        st.info("Carga ambos libros Excel para generar el tablero.")
        st.stop()
    try:
        data, diagnostico = cargar_reportes_excel(
            archivo_productos, archivo_ventas
        )
    except ValueError as error:
        st.error(str(error))
        st.stop()
    source_label = f"{archivo_productos.name} + {archivo_ventas.name}"
else:
    uploaded_file = st.sidebar.file_uploader(
        "Cargar exportación CSV", type=["csv"]
    )
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

data["fecha"] = pd.to_datetime(data["fecha"], errors="coerce").dt.normalize()
for column in (
    "cantidad_vendida",
    "stock",
    "stock_min",
    "stock_almacen",
):
    if column in data.columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")

invalid_rows = (
    data["fecha"].isna()
    | data["producto"].isna()
    | (data["sede"].isna() != data["stock"].isna())
    | (
        data["sede"].isna()
        & data["stock"].isna()
        & data["cantidad_vendida"].isna()
    )
)
if invalid_rows.any():
    st.warning(
        f"Se omitieron {int(invalid_rows.sum())} filas con fechas, productos o "
        "existencias inválidas."
    )
    data = data.loc[~invalid_rows].copy()
if data.empty:
    st.error("No hay filas válidas para mostrar.")
    st.stop()

if diagnostico:
    st.caption(
        f"Ventas importadas: {diagnostico['filas_ventas']:,} líneas, "
        f"{diagnostico['unidades_ventas']:,.0f} unidades en el libro; "
        f"{diagnostico['lineas_sin_coincidencia']:,} líneas no vinculadas "
        "de forma inequívoca al catálogo de inventario."
    )
    if diagnostico["filas_ventas_invalidas"]:
        st.warning(
            f"Se omitieron {diagnostico['filas_ventas_invalidas']} líneas de venta "
            "con fecha, producto o cantidad inválidos."
        )

if not any(
    column.lower().startswith("almacen") for column in data.columns
) and "stock_almacen" not in data.columns:
    st.sidebar.warning(
        "Sin columnas ALMACEN* no se sabe si hay unidades disponibles para reponer."
    )

dias_objetivo = st.sidebar.slider(
    "Días de cobertura objetivo", min_value=7, max_value=45, value=7
)
sedes_disponibles = sorted(set(SEDES) | set(data["sede"].dropna().unique()))
sede_seleccionada = st.sidebar.selectbox("Tienda", sedes_disponibles)
st.caption(f"Fuente: {source_label}")

reposicion = calcular_reposicion(data, dias_objetivo=dias_objetivo)
tienda = reposicion.loc[reposicion["Sede"] == sede_seleccionada].copy()
resumen = calcular_resumen_empresa(data)
fin_ventana = fecha_hoy(data)
inicio_ventana = fin_ventana - pd.Timedelta(days=29)
ventas_ventana = data.loc[
    data["fecha"].between(inicio_ventana, fin_ventana)
    & data["cantidad_vendida"].notna()
].groupby("producto")["cantidad_vendida"].sum()
productos_estimados = set(reposicion["Producto"])
productos_sin_estimacion = ventas_ventana.index.difference(productos_estimados)
unidades_sin_estimacion = float(ventas_ventana.reindex(productos_sin_estimacion).sum())
if unidades_sin_estimacion:
    st.warning(
        f"No se pudo estimar la demanda por tienda para "
        f"{len(productos_sin_estimacion)} productos "
        f"({unidades_sin_estimacion:,.0f} unidades vendidas): falta una categoría "
        "que coincida con el perfil de surtido de las tiendas."
    )

tab_tienda, tab_empresa, tab_ranking = st.tabs(
    ["Qué necesita cada tienda", "Resumen empresa", "Más vendidos"]
)

with tab_tienda:
    alertas = tienda.loc[tienda["Estado"].isin(["Crítico", "Atención"])].copy()
    criticos = int((alertas["Estado"] == "Crítico").sum())
    atencion = int((alertas["Estado"] == "Atención").sum())
    unidades = int(alertas["A reponer"].sum())

    columna1, columna2, columna3 = st.columns(3)
    columna1.metric("Críticos", f"{criticos:,}")
    columna2.metric("En atención", f"{atencion:,}")
    columna3.metric("Unidades a reponer", f"{unidades:,}")
    st.subheader(f"Necesidades de {sede_seleccionada}")
    st.caption("Venta estimada según el surtido de la tienda")

    alertas["Estado"] = alertas["Estado"].map(mostrar_estado)
    st.dataframe(
        alertas,
        width="stretch",
        hide_index=True,
        column_config={
            "Venta estimada/día": st.column_config.NumberColumn(format="%.2f"),
            "Peso surtido": st.column_config.NumberColumn(format="%.1%"),
            "Cobertura estimada (días)": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    hoy = fecha_hoy(data).date().isoformat()
    csv = alertas.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Descargar lista de la tienda",
        data=csv,
        file_name=f"reposicion_{sede_seleccionada}_{hoy}.csv",
        mime="text/csv",
    )

with tab_empresa:
    st.caption("Ventas agregadas de todas las tiendas; estos importes no se estiman.")
    st.dataframe(
        resumen,
        width="stretch",
        hide_index=True,
        column_config={
            "Venta empresa/día": st.column_config.NumberColumn(format="%.2f"),
        },
    )

with tab_ranking:
    st.caption("Ventas de los últimos 30 días, agregadas a nivel empresa.")
    nivel = st.selectbox("Agrupar por", ["Producto", "Categoría"])
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

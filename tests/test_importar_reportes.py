import pandas as pd
import pytest

from importar_reportes import normalizar_reportes
from reposicion import calcular_ranking, calcular_reposicion


def crear_reportes():
    productos = pd.DataFrame([
        {
            "Codigo": "A1",
            "Articulo": "Laptop base",
            "Categoria": "LAPTOP",
            "Subcategoria": "GAMER",
            "TIENDA 140 PRINCIPAL": 0,
            "TIENDA 144": 0,
            "TIENDA 147": 0,
            "TIENDA 209C": 1,
            "TIENDA 129": 1,
            "ALMACEN 235": 2,
            "ALMACEN 142": 1,
        },
        {
            "Codigo": "A2",
            "Articulo": "Laptop de perfil",
            "Categoria": "LAPTOP",
            "Subcategoria": "GAMER",
            "TIENDA 140 PRINCIPAL": 0,
            "TIENDA 144": 0,
            "TIENDA 147": 0,
            "TIENDA 209C": 5,
            "TIENDA 129": 0,
            "ALMACEN 235": 0,
            "ALMACEN 142": 0,
        },
    ])
    tienda = pd.DataFrame([
        {
            "Codigo1": "A1",
            "Ubicacion": "TIENDA 209C",
            "StockMin": 8,
        },
    ])
    ventas = pd.DataFrame([
        {
            "Fecha Venta": pd.Timestamp("2026-11-18 10:30"),
            "Producto": "Laptop base",
            "PartNumber": "A1",
            "Tipo": "GAMER",
            "Cantidad": 30,
        },
        {
            "Fecha Venta": pd.Timestamp("2026-11-18 11:30"),
            "Producto": "Laptop sin stock reportado",
            "PartNumber": "VIEJO-01",
            "Tipo": "LAPTOP",
            "Cantidad": 15,
        },
    ])
    return productos, tienda, ventas


def test_importa_stock_minimo_almacenes_y_ventas_sin_tienda():
    data, diagnostico = normalizar_reportes(*crear_reportes())

    filas_venta = data.loc[data["cantidad_vendida"].notna()]
    fila_stock = data.loc[
        (data["producto"] == "Laptop base") & (data["sede"] == "209C")
    ].iloc[0]

    assert filas_venta["sede"].isna().all()
    assert filas_venta["cantidad_vendida"].sum() == 45
    assert fila_stock["stock_min"] == 8
    assert fila_stock["ALMACEN total"] == 3
    assert diagnostico["productos_sin_coincidencia"] == 1


def test_importador_reparte_ventas_por_perfil_y_no_por_vendedor():
    data, _ = normalizar_reportes(*crear_reportes())
    resultado = calcular_reposicion(data)
    ranking = calcular_ranking(data, nivel="Producto")

    laptop = resultado.loc[resultado["Producto"] == "Laptop base"]
    assert set(laptop["Sede"]) == {"209C", "129"}
    assert laptop["Venta estimada/día"].sum() == pytest.approx(1)

    sin_stock = resultado.loc[
        resultado["Producto"] == "Laptop sin stock reportado"
    ]
    assert set(sin_stock["Sede"]) == {"209C", "129"}
    assert set(sin_stock["Stock tienda"]) == {0}
    assert sin_stock["Venta estimada/día"].sum() == pytest.approx(0.5)
    assert ranking["Unidades vendidas"].sum() == 45
    assert set(ranking["Producto"]) == {
        "Laptop base",
        "Laptop sin stock reportado",
    }

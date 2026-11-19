import math

import pandas as pd

from reposicion import calcular_reposicion


def crear_dataset(stock_final, ventas, stock_almacen=None):
    hoy = pd.Timestamp("2026-11-19")
    filas = []
    for numero in range(30):
        fecha = hoy - pd.Timedelta(days=29 - numero)
        fila = {
            "fecha": fecha,
            "sede": "140 Principal",
            "producto": "Producto prueba",
            "categoria": "Prueba",
            "stock": stock_final if numero == 29 else max(0, stock_final + (29 - numero)),
            "cantidad_vendida": ventas[numero],
        }
        if stock_almacen is not None:
            fila["stock_almacen"] = stock_almacen
        filas.append(fila)
    return pd.DataFrame(filas)


def test_producto_de_tres_unidades_que_se_agota():
    data = crear_dataset(stock_final=0, ventas=[1] * 30)
    fila = calcular_reposicion(data).iloc[0]

    assert fila["Venta/día (30d)"] == 1
    assert fila["Cobertura (días)"] == 0
    assert fila["A reponer"] == 7
    assert fila["Estado"] == "Crítico"


def test_producto_sin_ventas_tiene_cobertura_infinita():
    data = crear_dataset(stock_final=5, ventas=[0] * 30)
    fila = calcular_reposicion(data).iloc[0]

    assert fila["Venta/día (30d)"] == 0
    assert math.isinf(fila["Cobertura (días)"])
    assert fila["Estado"] == "Sin rotación"


def test_producto_con_sobrestock():
    data = crear_dataset(stock_final=100, ventas=[1] * 30)
    fila = calcular_reposicion(data).iloc[0]

    assert fila["Cobertura (días)"] == 100
    assert fila["Estado"] == "Sobrestock"


def test_stock_almacen_limitando_y_sin_stock_almacen():
    data_con_almacen = crear_dataset(stock_final=1, ventas=[2] * 30, stock_almacen=4)
    fila = calcular_reposicion(data_con_almacen, dias_objetivo=7).iloc[0]

    assert fila["Stock almacén"] == 4
    assert fila["Se puede reponer"] == 4
    assert fila["A reponer"] == 13
    assert fila["Disponibilidad"] == "Sin stock en almacén"

    data_sin_almacen = crear_dataset(stock_final=1, ventas=[2] * 30)
    resultado = calcular_reposicion(data_sin_almacen)

    assert "Stock almacén" not in resultado.columns
    assert "Se puede reponer" not in resultado.columns

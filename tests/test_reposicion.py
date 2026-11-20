import pytest
import pandas as pd

from reposicion import calcular_reposicion, calcular_resumen_empresa, calcular_ranking


FECHA = pd.Timestamp("2026-11-19")


def crear_datos():
    return []


def agregar_producto(
    filas, producto, categoria, sede, stock, vendido=0, stock_min=0,
    almacen=0, almacen_2=0,
):
    filas.append({
        "fecha": FECHA,
        "sede": sede,
        "producto": producto,
        "categoria": categoria,
        "stock": stock,
        "stock_min": stock_min,
        "cantidad_vendida": vendido,
        "ALMACEN 1": almacen,
        "ALMACEN 2": almacen_2,
    })


def datos_con_perfil(base_en_140=4, base_en_147=1, venta=30, almacen=0):
    filas = crear_datos()
    for indice in range(base_en_140):
        agregar_producto(filas, f"Perfil 140-{indice}", "Periféricos", "140 Principal", 10)
    for indice in range(base_en_147):
        agregar_producto(filas, f"Perfil 147-{indice}", "Periféricos", "147", 10)
    agregar_producto(
        filas, "Producto agotado", "Periféricos", "144", 0,
        vendido=venta, almacen=almacen,
    )
    agregar_producto(
        filas, "Producto agotado", "Periféricos", "147", 0,
        almacen=almacen,
    )
    return pd.DataFrame(filas)


def test_producto_vendido_ausente_se_reparte_entre_candidatas_y_es_critico():
    resultado = calcular_reposicion(datos_con_perfil())
    producto = resultado.loc[resultado["Producto"] == "Producto agotado"]

    assert set(producto["Sede"]) == {"140 Principal", "147"}
    assert set(producto["Estado"]) == {"Crítico"}
    assert set(producto["Stock tienda"]) == {0}
    assert producto["Venta estimada/día"].sum() == pytest.approx(1)


def test_categoria_especializada_asigna_venta_solo_a_las_tiendas_con_surtido():
    filas = []
    agregar_producto(filas, "Laptop base 1", "Laptops", "209C", 5)
    agregar_producto(filas, "Laptop base 2", "Laptops", "129", 5)
    agregar_producto(filas, "Laptop agotada", "Laptops", "140 Principal", 0, vendido=30)

    resultado = calcular_reposicion(pd.DataFrame(filas))
    producto = resultado.loc[resultado["Producto"] == "Laptop agotada"]

    assert set(producto["Sede"]) == {"209C", "129"}
    assert producto["Venta estimada/día"].tolist() == pytest.approx([0.5, 0.5])


def test_tienda_que_agota_producto_sigue_como_candidata_por_su_categoria():
    resultado = calcular_reposicion(datos_con_perfil())
    producto = resultado.loc[resultado["Producto"] == "Producto agotado"]

    agotada = producto.loc[producto["Sede"] == "147"].iloc[0]
    assert agotada["Stock tienda"] == 0
    assert agotada["Peso surtido"] == 0.2


def test_pesos_normalizados_y_venta_estimada_conservan_total_empresa():
    resultado = calcular_reposicion(datos_con_perfil(venta=90))
    producto = resultado.loc[resultado["Producto"] == "Producto agotado"]

    assert producto["Peso surtido"].sum() == pytest.approx(1)
    assert producto["Venta estimada/día"].sum() == pytest.approx(3)


def test_accion_compra_si_almacen_no_tiene_existencias():
    resultado = calcular_reposicion(datos_con_perfil(almacen=0))
    producto = resultado.loc[resultado["Producto"] == "Producto agotado"]

    assert set(producto["Acción"]) == {"Comprar/pedir"}


def test_stock_minimo_de_tienda_sobrescribe_minimo_calculado():
    filas = []
    agregar_producto(filas, "Único", "Laptops", "209C", 4, vendido=30, stock_min=9)
    filas[0]["StockMin"] = filas[0].pop("stock_min")

    resultado = calcular_reposicion(pd.DataFrame(filas))

    assert resultado.iloc[0]["Mínimo"] == 9


def test_resumen_y_ranking_mantienen_ventas_exactas_de_empresa():
    datos = datos_con_perfil(venta=30, almacen=4)
    datos.loc[
        datos["producto"] == "Producto agotado", "ALMACEN 2"
    ] = 3

    resumen = calcular_resumen_empresa(datos)
    agotado = resumen.loc[resumen["Producto"] == "Producto agotado"].iloc[0]
    ranking = calcular_ranking(datos, nivel="Producto")
    venta = ranking.loc[ranking["Producto"] == "Producto agotado"].iloc[0]

    assert agotado["Venta empresa/día"] == 1
    assert agotado["Stock almacén"] == 7
    assert agotado["Estado"] == "Solo en almacén"
    assert venta["Unidades vendidas"] == 30


def test_resumen_marca_agotado_en_todo_el_sistema():
    resumen = calcular_resumen_empresa(datos_con_perfil(almacen=0))
    producto = resumen.loc[resumen["Producto"] == "Producto agotado"].iloc[0]

    assert producto["Stock total sistema"] == 0
    assert producto["Estado"] == "Agotado en todo el sistema"

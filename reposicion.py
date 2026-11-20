"""Cálculos de demanda estimada por surtido y resumen exacto de empresa."""

from math import ceil, inf

import pandas as pd

from config import (
    DIAS_MINIMO,
    DIAS_VENTA_30,
    MINIMOS_POR_PRODUCTO,
    NIVEL_PERFIL,
    PISO_MINIMO_UNIDADES,
    SEDES,
    UMBRAL_PESO,
)


def fecha_hoy(data):
    fechas = pd.to_datetime(data["fecha"], errors="coerce").dropna()
    if fechas.empty:
        raise ValueError("El dataset no contiene fechas válidas.")
    return fechas.max().normalize()


def _datos_limpios(data):
    datos = data.copy()
    if "stock_min" not in datos.columns:
        columna_minimo = next(
            (columna for columna in datos.columns if columna.lower() == "stockmin"),
            None,
        )
        if columna_minimo:
            datos = datos.rename(columns={columna_minimo: "stock_min"})
    datos["fecha"] = pd.to_datetime(datos["fecha"], errors="coerce").dt.normalize()
    datos["cantidad_vendida"] = pd.to_numeric(
        datos["cantidad_vendida"], errors="coerce"
    )
    datos["stock"] = pd.to_numeric(datos["stock"], errors="coerce")
    if "stock_min" in datos.columns:
        datos["stock_min"] = pd.to_numeric(datos["stock_min"], errors="coerce")
    datos = datos.dropna(subset=["fecha", "producto"])
    return datos.sort_values("fecha", kind="stable")


def _ventas_empresa(data, hoy):
    inicio = hoy - pd.Timedelta(days=DIAS_VENTA_30 - 1)
    ventana = data.loc[
        data["fecha"].between(inicio, hoy) & data["cantidad_vendida"].notna()
    ]
    unidades = ventana.groupby("producto")["cantidad_vendida"].sum()
    return unidades / DIAS_VENTA_30


def _inventario_actual(data):
    filas = data.dropna(subset=["sede", "stock"]).drop_duplicates(
        ["producto", "sede"], keep="last"
    )
    if "stock_min" in data.columns:
        minimos = data.loc[
            data["sede"].notna()
            & data["stock_min"].notna()
            & (data["stock_min"] > 0),
            ["producto", "sede", "fecha", "stock_min"],
        ].drop_duplicates(["producto", "sede"], keep="last")
        minimos = minimos.set_index(["producto", "sede"])["stock_min"]
        filas = filas.set_index(["producto", "sede"])
        filas["stock_min"] = minimos.reindex(filas.index)
        return filas
    return filas.set_index(["producto", "sede"])


def _peso_categoria(inventario, nivel, sedes):
    if nivel not in inventario.columns:
        raise ValueError(
            f"NIVEL_PERFIL='{nivel}' requiere la columna '{nivel}' en los datos."
        )

    pesos = {}
    inventario_con_stock = inventario.loc[inventario["stock"] > 0]
    grupos = inventario_con_stock.groupby(nivel, dropna=True)
    for categoria, productos in grupos:
        por_sede = productos.reset_index().groupby("sede")["producto"].nunique()
        total = int(por_sede.sum())
        pesos[categoria] = {
            sede: (float(por_sede.get(sede, 0)) / total if total else 0.0)
            for sede in sedes
        }
    return pesos


def _stock_almacen_por_producto(data):
    columnas = [
        columna
        for columna in data.columns
        if columna.lower().startswith("almacen")
    ]
    if not columnas and "stock_almacen" in data.columns:
        columnas = ["stock_almacen"]
    if not columnas:
        return None

    fechas = data[["fecha", "producto"] + columnas].copy()
    for columna in columnas:
        fechas[columna] = pd.to_numeric(fechas[columna], errors="coerce")
    fechas["_stock_almacen"] = fechas[columnas].fillna(0).clip(lower=0).sum(axis=1)
    fechas = fechas.loc[fechas[columnas].notna().any(axis=1)]
    fechas = fechas.sort_values("fecha", kind="stable")
    # Las existencias del almacén se repiten a veces en cada fila de tienda.
    # Tomar la última observación por producto evita contarlas varias veces.
    ultimo = fechas.drop_duplicates("producto", keep="last").set_index("producto")
    return ultimo["_stock_almacen"].astype(float)


def _accion_almacen(a_reponer, stock_almacen):
    if stock_almacen is None:
        return "Sin dato de almacén"
    if a_reponer <= 0:
        return "Sin reposición"
    if stock_almacen <= 0:
        return "Comprar/pedir"
    if stock_almacen >= a_reponer:
        return "Traer de almacén"
    return "Traer parcial"


def _minimo_producto(producto, stock_min, venta_diaria):
    if pd.notna(stock_min) and float(stock_min) > 0:
        return int(ceil(float(stock_min)))
    return int(
        MINIMOS_POR_PRODUCTO.get(
            producto,
            max(PISO_MINIMO_UNIDADES, ceil(venta_diaria * DIAS_MINIMO)),
        )
    )


def calcular_reposicion(
    data, dias_objetivo=7, nivel_perfil=None, umbral_peso=None
):
    """Calcula demanda estimada y reposición por tienda, no por vendedor."""
    columnas_vacias = [
        "Producto", "Categoría", "Sede", "Stock tienda", "Mínimo",
        "Venta estimada/día", "Peso surtido", "Cobertura estimada (días)",
        "A reponer", "Estado", "Stock almacén", "Acción",
    ]
    if data.empty:
        return pd.DataFrame(columns=columnas_vacias)

    datos = _datos_limpios(data)
    if datos.empty:
        return pd.DataFrame(columns=columnas_vacias)

    hoy = fecha_hoy(datos)
    venta_empresa = _ventas_empresa(datos, hoy)
    inventario = _inventario_actual(datos)
    nivel = nivel_perfil or NIVEL_PERFIL
    umbral = UMBRAL_PESO if umbral_peso is None else umbral_peso
    sedes = list(dict.fromkeys(SEDES + datos["sede"].dropna().tolist()))
    pesos_por_categoria = _peso_categoria(inventario, nivel, sedes)
    almacen = _stock_almacen_por_producto(datos)

    categorias_perfil = (
        datos.dropna(subset=[nivel])
        .drop_duplicates("producto", keep="last")
        .set_index("producto")[nivel]
        .to_dict()
    )
    categorias = (
        datos.dropna(subset=["categoria"])
        .drop_duplicates("producto", keep="last")
        .set_index("producto")["categoria"]
        .to_dict()
    )
    productos = sorted(set(venta_empresa.index) | set(inventario.index.get_level_values(0)))
    claves_stock = set(inventario.index.tolist())
    filas = []

    for producto in productos:
        categoria_perfil = categorias_perfil.get(producto)
        categoria = categorias.get(producto, "")
        perfil = pesos_por_categoria.get(categoria_perfil, {})
        candidatas = []
        for sede in sedes:
            stock_sede = inventario.loc[(producto, sede)] if (producto, sede) in claves_stock else None
            stock_actual = (
                max(0.0, float(stock_sede["stock"]))
                if stock_sede is not None and pd.notna(stock_sede["stock"])
                else 0.0
            )
            if stock_actual > 0 or perfil.get(sede, 0.0) >= umbral:
                candidatas.append((sede, stock_actual, perfil.get(sede, 0.0), stock_sede))

        peso_total = sum(peso for _, _, peso, _ in candidatas)
        if not candidatas or peso_total <= 0:
            continue

        venta_diaria_empresa = float(venta_empresa.get(producto, 0.0))
        stock_almacen = (
            max(0, int(ceil(float(almacen.get(producto, 0)))))
            if almacen is not None
            else None
        )
        for sede, stock_actual, peso, stock_sede in candidatas:
            peso_normalizado = peso / peso_total
            venta_estimada = venta_diaria_empresa * peso_normalizado
            cobertura = stock_actual / venta_estimada if venta_estimada > 0 else inf
            minimo_existente = (
                stock_sede.get("stock_min")
                if stock_sede is not None and "stock_min" in stock_sede.index
                else None
            )
            minimo = _minimo_producto(producto, minimo_existente, venta_estimada)

            if venta_estimada == 0:
                estado = "Sin rotación"
            elif stock_actual <= 0 or cobertura < 2 or stock_actual <= 1:
                estado = "Crítico"
            elif stock_actual < minimo or cobertura < 5:
                estado = "Atención"
            elif cobertura > 45:
                estado = "Sobrestock"
            else:
                estado = "Normal"

            reponer = max(0, ceil(venta_estimada * dias_objetivo) - int(stock_actual))
            filas.append({
                "Producto": producto,
                "Categoría": categoria or "",
                "Sede": sede,
                "Stock tienda": int(stock_actual),
                "Mínimo": minimo,
                "Venta estimada/día": venta_estimada,
                "Peso surtido": peso_normalizado,
                "Cobertura estimada (días)": cobertura,
                "A reponer": reponer,
                "Estado": estado,
                "Stock almacén": stock_almacen,
                "Acción": _accion_almacen(reponer, stock_almacen),
            })

    resultado = pd.DataFrame(filas, columns=columnas_vacias)
    if not resultado.empty:
        urgencia = {"Crítico": 0, "Atención": 1, "Sin rotación": 2, "Normal": 3, "Sobrestock": 4}
        resultado["_urgencia"] = resultado["Estado"].map(urgencia)
        resultado["_cobertura"] = resultado["Cobertura estimada (días)"].replace(inf, 999999)
        resultado = resultado.sort_values(
            ["_urgencia", "_cobertura", "Producto", "Sede"]
        ).drop(columns=["_urgencia", "_cobertura"])
    return resultado.reset_index(drop=True)


def calcular_resumen_empresa(data):
    """Devuelve ventas y stock exactos a nivel empresa, sin estimar tiendas."""
    columnas = [
        "Producto", "Categoría", "Venta empresa/día", "Stock tiendas",
        "Stock almacén", "Stock total sistema", "Estado",
    ]
    if data.empty:
        return pd.DataFrame(columns=columnas)
    datos = _datos_limpios(data)
    hoy = fecha_hoy(datos)
    ventas = _ventas_empresa(datos, hoy)
    inventario = _inventario_actual(datos)
    almacen = _stock_almacen_por_producto(datos)
    categorias = (
        datos.dropna(subset=["categoria"])
        .drop_duplicates("producto", keep="last")
        .set_index("producto")["categoria"]
        .to_dict()
    )
    productos = sorted(set(ventas.index) | set(inventario.index.get_level_values(0)))
    filas = []
    for producto in productos:
        stock_tiendas = int(
            inventario.xs(producto, level="producto")["stock"]
            .fillna(0).clip(lower=0).sum()
        ) if producto in inventario.index.get_level_values(0) else 0
        stock_almacen = (
            max(0, int(ceil(float(almacen.get(producto, 0)))))
            if almacen is not None
            else None
        )
        venta = float(ventas.get(producto, 0.0))
        if stock_almacen is None:
            estado = "Sin dato de almacén"
            stock_total_sistema = None
        elif stock_tiendas + stock_almacen == 0 and venta > 0:
            estado = "Agotado en todo el sistema"
            stock_total_sistema = 0
        elif stock_tiendas == 0 and stock_almacen > 0:
            estado = "Solo en almacén"
            stock_total_sistema = stock_almacen
        else:
            estado = "Disponible"
            stock_total_sistema = stock_tiendas + stock_almacen
        filas.append({
            "Producto": producto,
            "Categoría": categorias.get(producto, ""),
            "Venta empresa/día": venta,
            "Stock tiendas": stock_tiendas,
            "Stock almacén": stock_almacen,
            "Stock total sistema": stock_total_sistema,
            "Estado": estado,
        })
    return pd.DataFrame(filas, columns=columnas)


def calcular_ranking(data, nivel="Producto", dias=30):
    """Agrupa ventas de todas las tiendas por producto o categoría."""
    if nivel not in ("Producto", "Categoría"):
        raise ValueError("El ranking solo admite Producto o Categoría.")
    hoy = fecha_hoy(data)
    inicio = hoy - pd.Timedelta(days=dias - 1)
    datos = _datos_limpios(data)
    ventana = datos.loc[
        datos["fecha"].between(inicio, hoy)
        & datos["cantidad_vendida"].notna()
        & (datos["cantidad_vendida"] > 0)
    ].copy()
    columna = {"Producto": "producto", "Categoría": "categoria"}[nivel]
    return (
        ventana.groupby(columna, as_index=False)["cantidad_vendida"]
        .sum()
        .rename(columns={columna: nivel, "cantidad_vendida": "Unidades vendidas"})
        .sort_values("Unidades vendidas", ascending=False)
        .reset_index(drop=True)
    )

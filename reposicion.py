"""Funciones puras para calcular reposición por producto y sede."""

from math import ceil, inf

import pandas as pd

from config import (
    DIAS_MINIMO,
    DIAS_VENTA_30,
    DIAS_VENTA_7,
    MINIMOS_POR_PRODUCTO,
    PISO_MINIMO_UNIDADES,
)


ESTADOS = ("Crítico", "Atención", "Sobrestock", "Normal")


def fecha_hoy(data):
    fechas = pd.to_datetime(data["fecha"], errors="coerce").dropna()
    if fechas.empty:
        raise ValueError("El dataset no contiene fechas válidas.")
    return fechas.max().normalize()


def _promedio_en_ventana(data, hoy, dias):
    inicio = hoy - pd.Timedelta(days=dias - 1)
    ventana = data.loc[
        data["fecha"].between(inicio, hoy),
        ["fecha", "producto", "sede", "cantidad_vendida"],
    ].copy()
    if ventana.empty:
        return pd.Series(dtype="float64")

    ventas_diarias = (
        ventana.groupby(["producto", "sede", "fecha"], as_index=False)["cantidad_vendida"]
        .sum()
    )
    resultados = {}
    fechas = pd.date_range(inicio, hoy)
    for (producto, sede), grupo in ventas_diarias.groupby(["producto", "sede"]):
        por_fecha = grupo.set_index("fecha")["cantidad_vendida"].reindex(fechas, fill_value=0)
        resultados[(producto, sede)] = por_fecha.mean()
    return pd.Series(resultados, dtype="float64")


def _stock_final(data, columna="stock"):
    ordenado = data.sort_values("fecha")
    ultimo = ordenado.drop_duplicates(["producto", "sede"], keep="last")
    return ultimo.set_index(["producto", "sede"])[columna]


def calcular_reposicion(data, dias_objetivo=7):
    """Calcula el estado y la cantidad sugerida para cada producto/sede."""
    if data.empty:
        return pd.DataFrame(
            columns=[
                "Producto", "Categoría", "Sede", "Stock", "Mínimo",
                "Venta/día (30d)", "Venta/día (7d)", "Cobertura (días)",
                "A reponer", "Estado",
            ]
        )

    datos = data.copy()
    datos["fecha"] = pd.to_datetime(datos["fecha"], errors="coerce")
    datos = datos.dropna(subset=["fecha", "producto", "sede"])
    hoy = fecha_hoy(datos)
    venta_30 = _promedio_en_ventana(datos, hoy, DIAS_VENTA_30)
    venta_7 = _promedio_en_ventana(datos, hoy, DIAS_VENTA_7)
    stock = _stock_final(datos, "stock")

    categoria = (
        datos.sort_values("fecha")
        .drop_duplicates(["producto", "sede"], keep="last")
        .set_index(["producto", "sede"])["categoria"]
    )
    claves = sorted(stock.index)
    filas = []
    stock_almacen = _stock_final(datos, "stock_almacen") if "stock_almacen" in datos else None

    for producto, sede in claves:
        clave = (producto, sede)
        venta_diaria = float(venta_30.get(clave, 0.0) or 0.0)
        venta_7d = float(venta_7.get(clave, 0.0) or 0.0)
        stock_actual = max(0, float(stock.get(clave, 0.0) or 0.0))
        if venta_diaria == 0:
            cobertura = inf
            estado = "Sin rotación"
            minimo = max(PISO_MINIMO_UNIDADES, ceil(venta_diaria * DIAS_MINIMO))
        else:
            cobertura = stock_actual / venta_diaria
            minimo = MINIMOS_POR_PRODUCTO.get(
                producto,
                max(PISO_MINIMO_UNIDADES, ceil(venta_diaria * DIAS_MINIMO)),
            )
            if stock_actual <= 0 or cobertura < 2 or stock_actual <= 1:
                estado = "Crítico"
            elif stock_actual < minimo or cobertura < 5:
                estado = "Atención"
            elif cobertura > 45:
                estado = "Sobrestock"
            else:
                estado = "Normal"

        reponer = max(0, ceil(venta_diaria * dias_objetivo) - int(stock_actual))
        fila = {
            "Producto": producto,
            "Categoría": categoria.get(clave, ""),
            "Sede": sede,
            "Stock": int(stock_actual),
            "Mínimo": int(minimo),
            "Venta/día (30d)": round(venta_diaria, 2),
            "Venta/día (7d)": round(venta_7d, 2),
            "Cobertura (días)": cobertura,
            "A reponer": reponer,
            "Estado": estado,
        }
        if stock_almacen is not None:
            disponible = max(0, int(stock_almacen.get(clave, 0) or 0))
            fila["Stock almacén"] = disponible
            fila["Se puede reponer"] = min(reponer, disponible)
            fila["Disponibilidad"] = (
                "Sin stock en almacén"
                if reponer > disponible
                else "Stock suficiente"
            )
        filas.append(fila)

    resultado = pd.DataFrame(filas)
    if not resultado.empty:
        orden_estado = {"Crítico": 0, "Atención": 1, "Sin rotación": 2, "Normal": 3, "Sobrestock": 4}
        resultado["_urgencia"] = resultado["Estado"].map(orden_estado)
        resultado["_cobertura"] = resultado["Cobertura (días)"].replace(inf, 999999)
        resultado = resultado.sort_values(
            ["_urgencia", "_cobertura", "Producto", "Sede"],
            ascending=[True, True, True, True],
        ).drop(columns=["_urgencia", "_cobertura"])
    return resultado


def calcular_ranking(data, nivel="Producto", dias=30):
    """Agrupa las ventas de los últimos días por producto, categoría o sede."""
    hoy = fecha_hoy(data)
    inicio = hoy - pd.Timedelta(days=dias - 1)
    ventana = data.loc[data["fecha"].between(inicio, hoy)].copy()
    columna = {"Producto": "producto", "Categoría": "categoria", "Sede": "sede"}[nivel]
    return (
        ventana.groupby(columna, as_index=False)["cantidad_vendida"]
        .sum()
        .rename(columns={columna: nivel, "cantidad_vendida": "Unidades vendidas"})
        .sort_values("Unidades vendidas", ascending=True)
    )


def calcular_redistribucion(data, dias_objetivo=7):
    """Sugiere movimientos entre sedes sin llevar al donante bajo 30 días."""
    reposicion = calcular_reposicion(data, dias_objetivo=dias_objetivo)
    ventas = {}
    for _, fila in reposicion.iterrows():
        clave = (fila["Producto"], fila["Sede"])
        ventas[clave] = fila["Venta/día (30d)"]

    sugerencias = []
    productos = sorted(reposicion["Producto"].dropna().unique())
    for producto in productos:
        filas = reposicion.loc[reposicion["Producto"] == producto]
        receptores = filas.loc[
            filas["Estado"].isin(["Crítico", "Atención"])
        ].sort_values("Cobertura (días)")
        donantes = filas.loc[
            filas["Cobertura (días)"] > 45
        ].sort_values("Cobertura (días)", ascending=False)

        for _, receptor in receptores.iterrows():
            venta = float(receptor["Venta/día (30d)"])
            if venta <= 0:
                continue
            stock_receptor = int(receptor["Stock"])
            objetivo = ceil(venta * 7)
            necesita = max(0, objetivo - stock_receptor)
            cobertura_receptor = receptor["Cobertura (días)"]

            for _, donante in donantes.iterrows():
                if necesita < 2:
                    break
                venta_donante = float(donante["Venta/día (30d)"])
                if venta_donante <= 0:
                    continue
                stock_donante = int(donante["Stock"])
                disponible = stock_donante - ceil(venta_donante * 30)
                mover = min(necesita, disponible)
                if mover < 2:
                    continue

                stock_donante -= mover
                stock_receptor += mover
                necesita -= mover
                cobertura_donante = stock_donante / venta_donante
                cobertura_receptora = stock_receptor / venta
                sugerencias.append({
                    "Origen": donante["Sede"],
                    "Destino": receptor["Sede"],
                    "Producto": producto,
                    "Mover": mover,
                    "Cobertura origen antes": round(donante["Cobertura (días)"], 1),
                    "Cobertura origen después": round(cobertura_donante, 1),
                    "Cobertura destino antes": round(cobertura_receptor, 1),
                    "Cobertura destino después": round(cobertura_receptora, 1),
                })
                receptor["Stock"] = stock_receptor
                donantes.loc[
                    donantes["Sede"] == donante["Sede"], "Stock"
                ] = stock_donante
    return pd.DataFrame(sugerencias)

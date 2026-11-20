"""Carga los reportes Excel de productos e inventario y ventas."""

import re
import unicodedata

import pandas as pd


_SEDES = {
    "TIENDA 140 PRINCIPAL": "140 Principal",
    "TIENDA 144": "144",
    "TIENDA 147": "147",
    "TIENDA 209C": "209C",
    "TIENDA 129": "129",
}


def _texto_normalizado(valor):
    if pd.isna(valor):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = texto.encode("ascii", "ignore").decode("ascii").upper()
    return re.sub(r"[^A-Z0-9]+", " ", texto).strip()


def _codigo_normalizado(valor):
    if pd.isna(valor):
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip().upper()


def _sede_normalizada(valor):
    return _SEDES.get(_texto_normalizado(valor), "")


def _numero_no_negativo(valor):
    numero = pd.to_numeric(valor, errors="coerce")
    return max(0.0, float(numero)) if pd.notna(numero) else 0.0


def _exigir_columnas(data, requeridas, nombre_hoja):
    faltantes = set(requeridas).difference(data.columns)
    if faltantes:
        raise ValueError(
            f"La hoja '{nombre_hoja}' no contiene las columnas requeridas: "
            + ", ".join(sorted(faltantes))
        )


def cargar_reportes_excel(reporte_productos, reporte_ventas):
    """Convierte los dos libros reales al esquema usado por los cálculos."""
    with pd.ExcelFile(reporte_productos) as libro_productos:
        productos = libro_productos.parse(
            "Stock x Tienda", dtype={"Codigo": str}
        )
        tienda = libro_productos.parse("Tienda", dtype={"Codigo1": str})
    with pd.ExcelFile(reporte_ventas) as libro_ventas:
        ventas = libro_ventas.parse(
            "Datos Planos", dtype={"PartNumber": str}
        )
    return normalizar_reportes(productos, tienda, ventas)


def normalizar_reportes(productos, tienda, ventas):
    """Une inventario y ventas sin atribuir una venta a una tienda."""
    productos = productos.rename(columns=lambda nombre: str(nombre).strip())
    tienda = tienda.rename(columns=lambda nombre: str(nombre).strip())
    ventas = ventas.rename(columns=lambda nombre: str(nombre).strip())

    _exigir_columnas(
        productos,
        {"Codigo", "Articulo", "Categoria", "Subcategoria"},
        "Stock x Tienda",
    )
    _exigir_columnas(
        tienda,
        {"Codigo1", "Ubicacion", "StockMin"},
        "Tienda",
    )
    _exigir_columnas(
        ventas,
        {"Fecha Venta", "Producto", "PartNumber", "Tipo", "Cantidad"},
        "Datos Planos",
    )

    columnas_tienda = [
        columna
        for columna in productos.columns
        if columna.upper().startswith("TIENDA ")
    ]
    columnas_almacen = [
        columna
        for columna in productos.columns
        if columna.upper().startswith("ALMACEN ")
    ]
    if not columnas_tienda:
        raise ValueError("La hoja 'Stock x Tienda' no tiene columnas de tiendas.")
    if not columnas_almacen:
        raise ValueError("La hoja 'Stock x Tienda' no tiene columnas ALMACEN*.")
    tiendas_por_columna = {
        columna: _sede_normalizada(columna) for columna in columnas_tienda
    }
    desconocidas = [
        columna for columna, sede in tiendas_por_columna.items() if not sede
    ]
    if desconocidas:
        raise ValueError(
            "Hay columnas de tienda que no se reconocen: "
            + ", ".join(desconocidas)
        )

    catalogo = productos.dropna(subset=["Codigo"]).copy()
    if catalogo.empty:
        raise ValueError("La hoja 'Stock x Tienda' no contiene productos.")
    catalogo["_codigo"] = catalogo["Codigo"].map(_codigo_normalizado)
    if catalogo["_codigo"].duplicated().any():
        raise ValueError("La hoja 'Stock x Tienda' contiene códigos duplicados.")
    catalogo = catalogo.set_index("_codigo", drop=False)

    productos_por_nombre = {}
    for codigo, fila in catalogo.iterrows():
        clave = _texto_normalizado(fila["Articulo"])
        if clave:
            productos_por_nombre.setdefault(clave, set()).add(codigo)

    codigos = set(catalogo.index)
    tipos_a_categorias = {}
    ventas_validas = ventas.copy()
    ventas_validas["Fecha Venta"] = pd.to_datetime(
        ventas_validas["Fecha Venta"], errors="coerce"
    )
    ventas_validas["Cantidad"] = pd.to_numeric(
        ventas_validas["Cantidad"], errors="coerce"
    )
    filas_ventas_originales = len(ventas_validas)
    ventas_validas = ventas_validas.dropna(
        subset=["Fecha Venta", "Producto", "Cantidad"]
    )
    ventas_validas = ventas_validas.loc[ventas_validas["Fecha Venta"].notna()]
    filas_ventas_invalidas = filas_ventas_originales - len(ventas_validas)
    if ventas_validas.empty:
        raise ValueError("La hoja 'Datos Planos' no contiene líneas de venta válidas.")
    ventas_validas["_codigo_encontrado"] = None
    ventas_validas["_ambiguo"] = False

    for indice, fila in ventas_validas.iterrows():
        candidatos = set(
            productos_por_nombre.get(_texto_normalizado(fila["Producto"]), set())
        )
        codigo_part_number = _codigo_normalizado(fila["PartNumber"])
        if codigo_part_number in codigos:
            candidatos.add(codigo_part_number)
        if len(candidatos) == 1:
            ventas_validas.at[indice, "_codigo_encontrado"] = next(iter(candidatos))
        elif len(candidatos) > 1:
            ventas_validas.at[indice, "_ambiguo"] = True

    for _, fila in ventas_validas.loc[
        ventas_validas["_codigo_encontrado"].notna()
    ].iterrows():
        tipo = _texto_normalizado(fila["Tipo"])
        categoria = catalogo.loc[fila["_codigo_encontrado"], "Categoria"]
        if tipo and pd.notna(categoria):
            tipos_a_categorias.setdefault(tipo, set()).add(str(categoria))

    fecha_corte = ventas_validas["Fecha Venta"].max().normalize()
    filas = []
    cantidades_minimas = {}
    for _, fila in tienda.iterrows():
        codigo = _codigo_normalizado(fila.get("Codigo1"))
        sede = _sede_normalizada(fila.get("Ubicacion"))
        stock_min = pd.to_numeric(fila.get("StockMin"), errors="coerce")
        if codigo and sede and pd.notna(stock_min) and stock_min > 0:
            cantidades_minimas[(codigo, sede)] = max(
                float(stock_min), cantidades_minimas.get((codigo, sede), 0.0)
            )

    for codigo, producto in catalogo.iterrows():
        almacen = sum(
            _numero_no_negativo(producto.get(columna))
            for columna in columnas_almacen
        )
        for columna, sede in tiendas_por_columna.items():
            stock = pd.to_numeric(producto.get(columna), errors="coerce")
            minimo = cantidades_minimas.get((codigo, sede), 0)
            filas.append({
                "fecha": fecha_corte,
                "producto": str(producto["Articulo"]).strip(),
                "categoria": producto["Categoria"],
                "subcategoria": producto["Subcategoria"],
                "sede": sede,
                "cantidad_vendida": None,
                "stock": _numero_no_negativo(stock),
                "stock_min": minimo,
                "ALMACEN total": almacen,
            })

    categorias_disponibles = {
        _texto_normalizado(valor): str(valor)
        for valor in catalogo["Categoria"].dropna().unique()
    }
    for _, fila in ventas_validas.iterrows():
        codigo = fila["_codigo_encontrado"]
        tipo = fila["Tipo"]
        if codigo:
            producto = catalogo.loc[codigo]
            nombre = str(producto["Articulo"]).strip()
            categoria = producto["Categoria"]
            subcategoria = producto["Subcategoria"]
        else:
            nombre = str(fila["Producto"]).strip()
            tipo_normalizado = _texto_normalizado(tipo)
            categorias_tipo = tipos_a_categorias.get(tipo_normalizado, set())
            if len(categorias_tipo) == 1:
                categoria = next(iter(categorias_tipo))
            else:
                categoria = categorias_disponibles.get(
                    tipo_normalizado, "Sin categoría"
                )
            subcategoria = (
                str(tipo).strip() if pd.notna(tipo) else "Sin subcategoría"
            )
        filas.append({
            "fecha": fila["Fecha Venta"].normalize(),
            "producto": nombre,
            "categoria": categoria if pd.notna(categoria) else "Sin categoría",
            "subcategoria": (
                subcategoria if pd.notna(subcategoria) else "Sin subcategoría"
            ),
            "sede": None,
            "cantidad_vendida": float(fila["Cantidad"]),
            "stock": None,
            "stock_min": None,
            "ALMACEN total": None,
        })

    normalizado = pd.DataFrame(filas)
    lineas_ambiguas = int(ventas_validas["_ambiguo"].sum())
    lineas_sin_coincidencia = int(
        ventas_validas["_codigo_encontrado"].isna().sum()
    )
    ventas_sin_coincidencia = ventas_validas.loc[
        ventas_validas["_codigo_encontrado"].isna()
    ]
    diagnostico = {
        "filas_ventas": int(len(ventas_validas)),
        "filas_ventas_invalidas": int(filas_ventas_invalidas),
        "unidades_ventas": float(ventas_validas["Cantidad"].sum()),
        "productos_ventas": int(ventas_validas["Producto"].nunique()),
        "codigos_mapeados": int(ventas_validas["_codigo_encontrado"].notna().sum()),
        "lineas_sin_coincidencia": lineas_sin_coincidencia,
        "productos_sin_coincidencia": int(
            ventas_sin_coincidencia["Producto"].nunique()
        ),
        "lineas_ambiguas": lineas_ambiguas,
        "fecha_ultima_venta": fecha_corte,
        "stock_tiendas": {
            sede: int(pd.to_numeric(productos[columna], errors="coerce").fillna(0).sum())
            for columna, sede in tiendas_por_columna.items()
        },
    }
    return normalizado, diagnostico

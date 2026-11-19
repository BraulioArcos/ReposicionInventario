"""Configuración de columnas de exportación y sedes disponibles."""

COLUMNAS = {
    "producto": "producto",
    "categoria": "categoria",
    "sede": "sede",
    "fecha": "fecha",
    "cantidad_vendida": "cantidad_vendida",
    "stock": "stock",
}

SEDES = ["140 Principal", "144", "147", "209C", "129"]

# Ventana de cálculo diaria para reposición.
DIAS_VENTA_30 = 30
DIAS_VENTA_7 = 7
PISO_MINIMO_UNIDADES = 2
DIAS_MINIMO = 7

# Saldos mínimos especiales por producto. Si un producto no aparece, se usa la
# regla general basada en PISO_MINIMO_UNIDADES y DIAS_MINIMO.
MINIMOS_POR_PRODUCTO = {
    # Ejemplo: "Tarjeta gráfica RTX": 1,
}


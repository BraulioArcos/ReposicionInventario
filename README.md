# Prototipo de reposición y análisis de ventas

Aplicación local e independiente para analizar exportaciones de ventas e
inventario. No se conecta ni modifica el sistema de ventas de la empresa.

## Estructura

- `datos/`: exportaciones reales locales, excluidas de Git.
- `datos_ejemplo/`: datos ficticios para pruebas.
- `config.py`: tiendas y parámetros del cálculo.
- `reposicion.py`: cálculos puros de estimación, reposición y resumen.
- `app.py`: tablero Streamlit.

## Ejecutar

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

El tablero abre el CSV de ejemplo por defecto y permite cargar una exportación
CSV con las columnas `fecha`, `producto`, `categoria`, `sede`,
`cantidad_vendida` y `stock`. `sede` identifica la tienda del registro de
inventario; **no se usa para asignar ventas a una tienda**. Si está disponible,
`stock_min` aplica el mínimo específico de esa tienda y producto. El stock de
almacén puede venir en `stock_almacen` o en una o más columnas cuyo nombre
empiece por `ALMACEN`; estas últimas se suman.

También se pueden seleccionar los dos reportes Excel y cargarlos juntos:

- `ReporteProductos.xlsx`: usa `Stock x Tienda` para existencias de las cinco
  tiendas y columnas `ALMACEN*`; usa `Tienda` para `StockMin`.
- `ReporteVentas1.xlsx`: usa las líneas de `Datos Planos` (`Fecha Venta`,
  `Producto`, `PartNumber`, `Tipo`, `Cantidad`). No lee ni usa `Usuario` o
  `Vendedor` para atribuir ventas.

El importador relaciona productos con el inventario por nombre normalizado o
por `PartNumber` que coincida exactamente con `Codigo`. Las ventas se conservan
a nivel empresa aunque no se encuentre una coincidencia. Para un producto sin
coincidencia, se intenta obtener la categoría desde `Tipo` solo si el cruce no
es ambiguo; si no se puede asignar un perfil, la venta permanece en el resumen
empresa y se advierte que no pudo estimarse por tienda.

## Criterio de demanda

La venta de cada producto se conoce exactamente a nivel empresa. La app suma
las unidades vendidas en todas las tiendas durante los últimos 30 días y divide
por 30 para obtener `venta_empresa/día`. No atribuye ventas a la tienda del
vendedor: los vendedores rotan entre tiendas y la exportación no identifica
fiablemente dónde ocurrió cada venta.

Por eso la vista **Qué necesita cada tienda** muestra una **demanda estimada**,
no una venta observada por tienda. La estimación reparte la venta empresa
proporcionalmente al surtido que cada tienda mantiene en la categoría del
producto (o subcategoría): productos distintos con stock positivo en esa tienda
divididos por el total de productos con stock positivo de ese perfil entre las
cinco tiendas. Un producto agotado sigue siendo candidato si la tienda conserva
un peso de perfil suficiente. Los pesos de las tiendas candidatas se
normalizan y, para los productos con perfil estimable, la suma de su demanda
estimada conserva la venta empresa. Si no hay categoría/perfil coincidente, la
venta permanece exacta en el resumen de empresa y el tablero advierte que no se
pudo estimar por tienda; no se asigna un perfil arbitrario.

## Vistas

- **Qué necesita cada tienda**: selector de tienda, alertas Crítico/Atención,
  venta estimada/día, cobertura estimada, stock, unidades a reponer, almacén y
  acción sugerida (`Traer de almacén`, `Traer parcial` o `Comprar/pedir`).
- **Resumen empresa**: stock exacto agregado de tiendas y almacenes frente a
  venta empresa/día; identifica productos agotados en todo el sistema y los
  disponibles solo en almacén.
- **Más vendidos**: ranking de unidades de los últimos 30 días por producto o
  categoría, agregado a nivel empresa.

La redistribución entre tiendas no se recomienda: queda para una mejora futura.
La acción de reposición contempla únicamente traer stock del almacén.

## Reglas y parámetros

Para cada tienda candidata, la cobertura es stock dividido por demanda
estimada/día. Los estados existentes son:

- **Crítico**: sin stock, stock de una unidad o menos, o cobertura menor de 2
  días.
- **Atención**: stock menor al mínimo o cobertura menor de 5 días.
- **Sobrestock**: cobertura mayor de 45 días.
- **Normal**: el resto.
- **Sin rotación**: venta estimada diaria igual a cero.

La cantidad sugerida es `max(0, ceil(demanda_estimada_día * días_objetivo) -
stock)`. Si `stock_min` de la tienda es mayor que cero, se usa como mínimo;
si no, se aplica `MINIMOS_POR_PRODUCTO` o el mínimo general.

En `config.py` se pueden ajustar:

- `SEDES`: las cinco tiendas consideradas.
- `NIVEL_PERFIL`: `categoria` por defecto; también admite `subcategoria` si los
  datos incluyen esa columna.
- `UMBRAL_PESO`: peso mínimo para incluir una tienda candidata, por defecto
  `0.15`.
- `PISO_MINIMO_UNIDADES`, `DIAS_MINIMO` y `MINIMOS_POR_PRODUCTO`.

El deslizante de días objetivo comienza en 7. Las estimaciones no consideran
tiempos de entrega ni pedidos en tránsito.

## Pruebas

```powershell
pytest
```

Las pruebas usan datasets pequeños creados en memoria; no requieren exportar ni
versionar datos reales.

# Prototipo de reposición y análisis de ventas

Aplicación local e independiente para analizar archivos exportados de ventas e
inventario. No se conecta ni modifica el sistema de ventas de la empresa.

## Estructura inicial

- `datos/`: exportaciones reales locales; está excluida de Git.
- `datos_ejemplo/`: datos ficticios para pruebas.
- `generar_ejemplo.py`: genera seis meses de ventas diarias para 30 productos
  y cinco sedes, todas tiendas.
- `config.py`: define las sedes disponibles y permite adaptar los encabezados
  del archivo real a los nombres esperados por la aplicación.
- `requirements.txt`: dependencias previstas para el prototipo.

## Generar los datos ficticios

```powershell
python --version
python generar_ejemplo.py
```

El archivo resultante es `datos_ejemplo/ventas_ejemplo.csv`. Se puede abrir en
Excel; sus fechas cubren los 183 días que terminan en la fecha de ejecución.
Contiene 27 450 filas (30 productos por cinco sedes por 183 días). El generador
usa una semilla fija para que los valores sean reproducibles y solo requiere
Python; todavía no hace falta instalar las dependencias de `requirements.txt`.

La columna `stock` representa las existencias simuladas al cierre de cada día.
Los nombres de columna del CSV coinciden inicialmente con los nombres
canónicos definidos en `config.py`.

## Ejecutar el tablero

Desde esta carpeta, instala las dependencias e inicia Streamlit:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

El tablero abre los datos ficticios por defecto. También permite cargar una
exportación CSV con las columnas canónicas de `config.py`. Las sugerencias de
reposición son estimaciones simples basadas en las ventas de los últimos 30
días y el stock registrado; no consideran tiempos de entrega ni pedidos en
tránsito.

## Ejecutar pruebas

```powershell
python -m pip install -r requirements.txt
pytest
```

## Reglas de reposición

La fecha más reciente del CSV se usa como “hoy”. Para cada producto y sede se
calculan:

- Venta/día: promedio de `cantidad_vendida` en los últimos 30 días.
- Venta/día 7d: promedio en los últimos 7 días.
- Stock actual: valor de `stock` del último día registrado.
- Cobertura: stock actual dividido por venta/día de 30 días. Si no hay ventas,
  la cobertura es infinita y el estado es `Sin rotación`.
- Mínimo: el mayor valor entre `PISO_MINIMO_UNIDADES` y
  `ceil(venta_diaria * DIAS_MINIMO)`. `MINIMOS_POR_PRODUCTO` puede reemplazar
  el mínimo para un producto concreto.
- Cantidad a reponer: `max(0, ceil(venta_diaria * dias_objetivo) - stock)`.

Estados:

- 🔴 Crítico: stock 0 o menor que 1, o cobertura menor de 2 días.
- 🟠 Atención: stock menor que el mínimo o cobertura menor de 5 días.
- 🟣 Sobrestock: cobertura mayor de 45 días.
- 🟢 Normal: el resto.
- Sin rotación: venta diaria de 30 días igual a cero.

La pestaña “Reposición de hoy” permite listar alertas, filtrar por sede y
categoría y descargar `reposicion_AAAA-MM-DD.csv`, agrupada por sede para el
almacén.

Si el CSV incluye `stock_almacen`, se muestran las unidades disponibles y cuánto
se puede reponer realmente. Sin esa columna, el tablero indica que no puede
confirmarse el abastecimiento. `stock_almacen` no forma parte de las columnas
requeridas.

## Parámetros

Se pueden ajustar en `config.py`:

- `SEDES`: sedes disponibles.
- `DIAS_VENTA_30`: ventana principal, por defecto 30.
- `DIAS_VENTA_7`: ventana corta, por defecto 7.
- `PISO_MINIMO_UNIDADES`: mínimo general, por defecto 2.
- `DIAS_MINIMO`: días usados para calcular el mínimo, por defecto 7.
- `MINIMOS_POR_PRODUCTO`: diccionario opcional, por ejemplo
  `{"Tarjeta gráfica RTX": 1}`.

El deslizante “Días de cobertura objetivo” tiene como valor inicial 7.

> Los archivos reales deben guardarse solo en `datos/`. No agregues
> exportaciones de la empresa a Git.

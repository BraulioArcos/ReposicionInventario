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
reposición son estimaciones simples basadas en las ventas del periodo y el
stock registrado; no consideran tiempos de entrega ni pedidos en tránsito.

> Los archivos reales deben guardarse solo en `datos/`. No agregues
> exportaciones de la empresa a Git.

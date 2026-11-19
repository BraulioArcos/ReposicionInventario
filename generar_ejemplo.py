"""Genera un CSV ficticio de ventas diarias e inventario para probar el prototipo."""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

from config import SEDES


PRODUCTOS = [
    ("Laptop Nova 14", "Computadoras", 1.8),
    ("Laptop Nova 15", "Computadoras", 1.3),
    ("Laptop Andina Pro", "Computadoras", 0.8),
    ("Tablet Prisma 10", "Tablets", 2.2),
    ("Tablet Prisma Mini", "Tablets", 1.7),
    ("Smartphone Kuntur X", "Smartphones", 4.5),
    ("Smartphone Kuntur Lite", "Smartphones", 5.5),
    ("Smartphone Sillar Pro", "Smartphones", 2.8),
    ("Monitor Inti 24", "Monitores", 2.0),
    ("Monitor Inti 27", "Monitores", 1.2),
    ("Teclado Mecánico Misti", "Periféricos", 3.2),
    ("Teclado Inalámbrico Qori", "Periféricos", 2.5),
    ("Mouse Óptico Colca", "Periféricos", 4.0),
    ("Mouse Gamer Chachani", "Periféricos", 2.1),
    ("Audífonos Yanahuara", "Audio", 3.4),
    ("Audífonos Inalámbricos Chili", "Audio", 2.7),
    ("Parlante Portátil Cotahuasi", "Audio", 1.6),
    ("Webcam Pampa 1080p", "Accesorios", 1.4),
    ("Disco SSD 1 TB", "Almacenamiento", 2.4),
    ("Disco SSD 2 TB", "Almacenamiento", 1.0),
    ("Disco Externo 2 TB", "Almacenamiento", 1.3),
    ("Memoria USB 128 GB", "Almacenamiento", 4.2),
    ("Router WiFi 6", "Redes", 1.5),
    ("Extensor WiFi", "Redes", 1.8),
    ("Impresora Tinta Sur", "Impresoras", 0.9),
    ("Tinta Negra Universal", "Impresoras", 3.0),
    ("Tinta Color Universal", "Impresoras", 2.2),
    ("Cargador USB-C 65W", "Accesorios", 3.8),
    ("Mochila Tech Arequipa", "Accesorios", 1.1),
    ("Adaptador USB-C Multipuerto", "Accesorios", 2.0),
]

TIPOS_REPOSICION = ["riesgo", "exceso"] + ["normal"] * 10

CAMPOS = [
    "fecha",
    "sede",
    "producto",
    "categoria",
    "stock",
    "cantidad_vendida",
    "stock_almacen",
]


def generar_filas(fecha_inicio, dias, semilla=42):
    """Produce un registro diario por producto y sede, con existencias simuladas."""
    azar = random.Random(semilla)
    inventario = {}
    inventario_almacen = {}
    combinaciones = []
    factores_sede = {sede: azar.uniform(0.75, 1.3) for sede in SEDES}

    indice = 0
    for producto, categoria, demanda_base in PRODUCTOS:
        for sede in SEDES:
            demanda_diaria = demanda_base * factores_sede[sede]
            perfil = TIPOS_REPOSICION[indice % len(TIPOS_REPOSICION)]
            intervalo = (
                azar.randint(20, 30)
                if perfil == "normal"
                else azar.randint(35, 50)
            )
            dias_stock = {
                "riesgo": azar.uniform(8, 12),
                "exceso": azar.uniform(60, 100),
                "normal": azar.uniform(18, 30),
            }[perfil]
            inventario[(producto, sede)] = max(
                1, round(demanda_diaria * dias_stock)
            )
            inventario_almacen[(producto, sede)] = azar.randint(0, 45)
            combinaciones.append(
                (producto, categoria, sede, demanda_diaria, perfil, intervalo)
            )
            indice += 1

    for numero_dia in range(dias):
        fecha = fecha_inicio + timedelta(days=numero_dia)
        factor_dia = 0.78 if fecha.weekday() == 6 else 1.0

        for (
            producto,
            categoria,
            sede,
            demanda_diaria,
            perfil,
            intervalo,
        ) in combinaciones:
            clave = (producto, sede)
            stock = inventario[clave]
            demanda = max(
                0,
                round(
                    azar.gauss(
                        demanda_diaria * factor_dia,
                        max(0.7, demanda_diaria * 0.45),
                    )
                ),
            )

            if perfil == "riesgo" and numero_dia == dias - 1:
                stock = max(stock, demanda + azar.randint(1, 5))

            vendido = min(stock, demanda)
            stock -= vendido

            if perfil == "riesgo":
                if numero_dia % intervalo == 0 and numero_dia < dias - 35:
                    objetivo = max(5, round(demanda_diaria * azar.uniform(12, 18)))
                    stock = max(stock, objetivo)
            elif perfil == "normal":
                if numero_dia > 0 and numero_dia % intervalo == 0:
                    if stock <= demanda_diaria * 12:
                        objetivo = max(
                            8, round(demanda_diaria * azar.uniform(20, 32))
                        )
                        stock = max(stock, objetivo)
            elif numero_dia > 0 and numero_dia % intervalo == 0:
                if stock <= demanda_diaria * 30:
                    objetivo = max(
                        20, round(demanda_diaria * azar.uniform(70, 100))
                    )
                    stock = max(stock, objetivo)

            inventario[clave] = stock
            yield {
                "fecha": fecha.isoformat(),
                "sede": sede,
                "producto": producto,
                "categoria": categoria,
                "stock": stock,
                "cantidad_vendida": vendido,
                "stock_almacen": inventario_almacen[clave],
            }


def generar_archivo(ruta_salida=None, fecha_fin=None, dias=183, semilla=42):
    """Escribe el ejemplo como CSV compatible con Excel."""
    if dias < 1:
        raise ValueError("La cantidad de días debe ser al menos 1.")

    fecha_fin = fecha_fin or date.today()
    fecha_inicio = fecha_fin - timedelta(days=dias - 1)
    ruta = ruta_salida or Path(__file__).parent / "datos_ejemplo" / "ventas_ejemplo.csv"
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)

    with ruta.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=CAMPOS)
        escritor.writeheader()
        escritor.writerows(generar_filas(fecha_inicio, dias, semilla))

    print(
        "CSV de ejemplo generado: "
        f"{ruta} ({len(PRODUCTOS)} productos, {len(SEDES)} sedes, {dias} días)"
    )


if __name__ == "__main__":
    generar_archivo()

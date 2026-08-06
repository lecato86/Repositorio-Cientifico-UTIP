import io
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from oafcare.database import get_db


def _fig_to_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def generar_g1(desde: str = None, hasta: str = None) -> bytes:
    """Line chart: daily interventions with trend line."""
    db = get_db()
    c = db.cursor()

    query = "SELECT fecha, SUM(atenciones) FROM atenciones_diarias"
    params = []

    if desde and hasta:
        query += " WHERE fecha BETWEEN ? AND ?"
        params = [desde, hasta]

    query += " GROUP BY fecha ORDER BY fecha"

    c.execute(query, params)
    datos = c.fetchall()

    fechas = [d[0] for d in datos]
    valores = [d[1] for d in datos]

    fig, ax = plt.subplots()

    if not valores:
        ax.text(0.5, 0.5, "Sin datos", ha="center")
    else:
        ax.plot(fechas, valores, marker="o")

        if len(valores) >= 2:
            x = np.arange(len(valores))
            coef = np.polyfit(x, valores, 1)
            tendencia = np.poly1d(coef)(x)
            ax.plot(fechas, tendencia, linestyle="--")

    ax.set_title("Atenciones por día")
    plt.xticks(rotation=45)

    return _fig_to_bytes(fig)


def generar_g2(desde: str = None, hasta: str = None) -> bytes:
    """Line chart: unique patients per day."""
    db = get_db()
    c = db.cursor()

    query = "SELECT fecha, COUNT(DISTINCT hc) FROM atenciones_diarias"
    params = []

    if desde and hasta:
        query += " WHERE fecha BETWEEN ? AND ?"
        params = [desde, hasta]

    query += " GROUP BY fecha ORDER BY fecha"

    c.execute(query, params)
    datos = c.fetchall()

    fechas = [d[0] for d in datos]
    valores = [d[1] for d in datos]

    fig, ax = plt.subplots()

    if not valores:
        ax.text(0.5, 0.5, "Sin datos", ha="center")
    else:
        ax.plot(fechas, valores, marker="o")

        if len(valores) >= 2:
            x = np.arange(len(valores))
            coef = np.polyfit(x, valores, 1)
            tendencia = np.poly1d(coef)(x)
            ax.plot(fechas, tendencia, linestyle="--")

    ax.set_title("Pacientes por día")
    plt.xticks(rotation=45)

    return _fig_to_bytes(fig)


def generar_g3() -> bytes:
    """Bar chart: active patients by respiratory support type."""
    db = get_db()
    c = db.cursor()

    c.execute("SELECT soporte, COUNT(*) FROM pacientes GROUP BY soporte")
    datos = c.fetchall()

    fig, ax = plt.subplots()

    if not datos:
        ax.text(0.5, 0.5, "Sin datos", ha="center")
    else:
        x = [d[0] for d in datos]
        y = [d[1] for d in datos]
        ax.bar(x, y)

    ax.set_title("Soporte ventilatorio")

    return _fig_to_bytes(fig)


def generar_g4() -> bytes:
    """Bar chart: pacientes por sala de derivación."""
    db = get_db()
    c = db.cursor()

    c.execute(
        "SELECT sala_derivacion, COUNT(*) FROM pacientes "
        "WHERE sala_derivacion IS NOT NULL AND sala_derivacion != '' "
        "GROUP BY sala_derivacion ORDER BY COUNT(*) DESC"
    )
    datos = c.fetchall()

    fig, ax = plt.subplots()

    if not datos:
        ax.text(0.5, 0.5, "Sin datos", ha="center")
    else:
        salas = [d[0] for d in datos]
        cantidad = [d[1] for d in datos]
        ax.bar(salas, cantidad)

    ax.set_title("Pacientes por sala de derivación")
    ax.set_xlabel("Sala de derivación")
    ax.set_ylabel("Cantidad")
    plt.xticks(rotation=45)

    return _fig_to_bytes(fig)


def generar_g5() -> bytes:
    """Bar chart: active patients by diagnosis."""
    db = get_db()
    c = db.cursor()

    c.execute(
        "SELECT diagnostico, COUNT(*) FROM pacientes "
        "WHERE diagnostico IS NOT NULL AND diagnostico != '' "
        "GROUP BY diagnostico ORDER BY COUNT(*) DESC"
    )
    datos = c.fetchall()

    fig, ax = plt.subplots()

    if not datos:
        ax.text(0.5, 0.5, "Sin datos", ha="center")
    else:
        patologias = [d[0] for d in datos]
        cantidad = [d[1] for d in datos]
        ax.bar(patologias, cantidad)

    ax.set_title("Patologías más frecuentes")
    ax.set_xlabel("Diagnóstico")
    ax.set_ylabel("Cantidad")
    plt.xticks(rotation=45)

    return _fig_to_bytes(fig)


def generar_evo_sala(hc: str) -> bytes:
    """Bar chart: days per room for one patient."""
    db = get_db()
    c = db.cursor()

    c.execute("""
        SELECT valor_nuevo, fecha
        FROM historial
        WHERE hc = ? AND campo = 'sala'
        ORDER BY fecha ASC
    """, (hc,))

    datos = c.fetchall()

    fig, ax = plt.subplots()

    if not datos:
        ax.text(0.5, 0.5, "Sin datos", ha="center")
    else:
        salas = {}
        for i in range(len(datos)):
            sala = datos[i][0]
            fecha_str = datos[i][1][:10]
            inicio = datetime.strptime(fecha_str, "%Y-%m-%d")

            if i + 1 < len(datos):
                fecha_fin_str = datos[i + 1][1][:10]
                fin = datetime.strptime(fecha_fin_str, "%Y-%m-%d")
            else:
                fin = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            dias = max((fin - inicio).days, 1)
            salas[sala] = salas.get(sala, 0) + dias

        ax.bar(salas.keys(), salas.values())

    ax.set_title("Días por sala")
    ax.set_ylabel("Días")

    return _fig_to_bytes(fig)


def generar_evo_sop(hc: str) -> bytes:
    """Bar chart: days per respiratory support for one patient."""
    db = get_db()
    c = db.cursor()

    c.execute("""
        SELECT valor_nuevo, fecha
        FROM historial
        WHERE hc = ? AND campo = 'soporte'
        ORDER BY fecha ASC
    """, (hc,))

    datos = c.fetchall()

    fig, ax = plt.subplots()

    if not datos:
        ax.text(0.5, 0.5, "Sin datos", ha="center")
    else:
        sop = {}
        for i in range(len(datos)):
            soporte = datos[i][0]
            fecha_str = datos[i][1][:10]
            inicio = datetime.strptime(fecha_str, "%Y-%m-%d")

            if i + 1 < len(datos):
                fecha_fin_str = datos[i + 1][1][:10]
                fin = datetime.strptime(fecha_fin_str, "%Y-%m-%d")
            else:
                fin = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            dias = max((fin - inicio).days, 1)
            sop[soporte] = sop.get(soporte, 0) + dias

        ax.bar(sop.keys(), sop.values())

    ax.set_title("Días por soporte")
    ax.set_ylabel("Días")

    return _fig_to_bytes(fig)

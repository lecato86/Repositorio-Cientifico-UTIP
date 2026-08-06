from oafcare.database import get_db
from oafcare.utils.soporte import SOPORTE_NIVELES, normalizar_soporte, soporte_en_fecha


def trayectoria_ventilatoria_data(hc: str) -> list[dict]:
    db = get_db()

    atenciones = db.execute(
        "SELECT fecha, atenciones FROM atenciones_diarias WHERE hc=? ORDER BY fecha ASC",
        (hc,),
    ).fetchall()

    historial = db.execute("""
        SELECT campo, valor_nuevo, fecha
        FROM historial
        WHERE hc=? AND campo IN ('soporte', 'sala')
        ORDER BY fecha ASC
    """, (hc,)).fetchall()

    paciente = db.execute(
        "SELECT soporte, sala FROM pacientes WHERE hc=?", (hc,)
    ).fetchone()

    fallback_soporte = paciente["soporte"] if paciente else ""
    fallback_sala = paciente["sala"] if paciente else ""

    eventos_soporte = [
        {"fecha": r["fecha"][:10], "valor_nuevo": r["valor_nuevo"]}
        for r in historial if r["campo"] == "soporte"
    ]
    eventos_sala = [
        {"fecha": r["fecha"][:10], "valor_nuevo": r["valor_nuevo"]}
        for r in historial if r["campo"] == "sala"
    ]

    result = []
    for row in atenciones:
        fecha = row["fecha"]
        soporte = normalizar_soporte(
            soporte_en_fecha(eventos_soporte, fecha, fallback_soporte)
        )
        if not soporte:
            continue
        sala = soporte_en_fecha(eventos_sala, fecha, fallback_sala)
        nivel = SOPORTE_NIVELES.get(soporte, 0)
        result.append({
            "fecha": fecha,
            "soporte": soporte,
            "soporte_nivel": nivel,
            "sala": sala,
            "atenciones": row["atenciones"],
        })

    return result

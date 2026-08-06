from datetime import datetime, timedelta
from oafcare.database import get_db, PACIENTE_COLUMNAS_INGRESO

# Columnas de `pacientes` que se sobrescriben siempre en el upsert (dato del
# día / identificación). Las columnas de ingreso (PACIENTE_COLUMNAS_INGRESO)
# se preservan con COALESCE cuando el llamador no las manda.
_CORE_COLS = ["nombre", "edad", "diagnostico", "soporte", "sala", "muestra",
              "tq", "estado", "ultima_actualizacion"]


def _a_entero(valor, default: int = 0) -> int:
    """Convierte a int de forma segura (Postgres no acepta '' en columna INTEGER)."""
    try:
        return int(str(valor).strip())
    except (ValueError, AttributeError, TypeError):
        return default


def get_paciente(hc: str):
    hc = (hc or "").strip()
    return get_db().execute(
        "SELECT * FROM pacientes WHERE hc = ?", (hc,)
    ).fetchone()


def get_pacientes_activos(hoy: str):
    return get_db().execute("""
        SELECT p.*,
               MAX(a.fecha) AS ultimo_registro,
               COALESCE(SUM(a.atenciones), 0) AS total_atenciones,
               MAX(CASE WHEN a.fecha = ? THEN 1 ELSE 0 END) AS activo_hoy
        FROM pacientes p
        LEFT JOIN atenciones_diarias a ON p.hc = a.hc
        WHERE p.estado = 'ACTIVO'
        GROUP BY p.hc
        ORDER BY activo_hoy DESC, ultimo_registro DESC, p.ultima_actualizacion DESC
    """, (hoy,)).fetchall()


def get_total_atenciones(hc: str) -> int:
    hc = (hc or "").strip()
    row = get_db().execute(
        "SELECT COALESCE(SUM(atenciones), 0) AS total FROM atenciones_diarias WHERE hc = ?",
        (hc,),
    ).fetchone()
    return row["total"] if row else 0


def get_pacientes_alta():
    return get_db().execute(
        "SELECT * FROM pacientes WHERE estado = 'ALTA' ORDER BY fecha_alta DESC"
    ).fetchall()


def get_ultima_entrada(hc: str):
    hc = (hc or "").strip()
    return get_db().execute("""
        SELECT a.id, a.hc, a.fecha, a.atenciones,
               p.nombre, p.edad, p.diagnostico, p.soporte, p.sala, p.muestra, p.tq
        FROM atenciones_diarias a
        JOIN pacientes p ON a.hc = p.hc
        WHERE a.hc = ?
        ORDER BY a.fecha DESC, a.id DESC
        LIMIT 1
    """, (hc,)).fetchone()


def insert_atencion(hc: str, fecha: str, atenciones) -> None:
    db = get_db()
    hc = (hc or "").strip()
    db.execute(
        "INSERT INTO atenciones_diarias (hc, fecha, atenciones) VALUES (?, ?, ?)",
        (hc, fecha, _a_entero(atenciones)),
    )
    db.commit()


def update_atencion(atencion_id: int, fecha: str, atenciones) -> None:
    db = get_db()
    db.execute(
        "UPDATE atenciones_diarias SET fecha=?, atenciones=? WHERE id=?",
        (fecha, _a_entero(atenciones), atencion_id),
    )
    db.commit()


def upsert_paciente(hc, nombre, edad, diagnostico, soporte, sala, muestra, tq,
                     estado, ultima_actualizacion, ingreso=None) -> None:
    """Inserta o actualiza un paciente.

    `ingreso` es un dict opcional con los campos del formulario de ingreso
    (claves = columnas en PACIENTE_COLUMNAS_INGRESO, ej. 'sexo', 'peso',
    'virus_vsr', 'comorbilidades', 'resultado_oaf', ...). Las columnas que no
    vengan en el dict (o vengan como None) se **conservan** vía COALESCE: así
    la edición de la última atención (que todavía no maneja estos campos) no
    pisa lo ya cargado. Las columnas core sí se sobrescriben siempre.
    """
    db = get_db()
    hc = (hc or "").strip()
    ingreso = ingreso or {}

    core = {
        "nombre": nombre, "edad": edad, "diagnostico": diagnostico,
        "soporte": soporte, "sala": sala, "muestra": muestra,
        "tq": int(bool(tq)), "estado": estado,
        "ultima_actualizacion": ultima_actualizacion,
    }
    ing = {col: ingreso.get(col) for col in PACIENTE_COLUMNAS_INGRESO}

    cols = ["hc"] + list(core.keys()) + list(ing.keys())
    valores = [hc] + list(core.values()) + list(ing.values())
    placeholders = ", ".join(["?"] * len(cols))
    set_core = ", ".join(f"{c}=excluded.{c}" for c in core)
    set_ing = ", ".join(
        f"{c}=COALESCE(excluded.{c}, pacientes.{c})" for c in ing
    )

    db.execute(
        f"INSERT INTO pacientes ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(hc) DO UPDATE SET {set_core}, {set_ing}",
        valores,
    )
    db.commit()


def get_mediciones_oaf(hc):
    hc = (hc or "").strip()
    return get_db().execute(
        "SELECT orden, tiempo, fc, fr, sato2, score_tal, fio2, flujo "
        "FROM mediciones_oaf WHERE hc = ? ORDER BY orden",
        (hc,),
    ).fetchall()


def guardar_mediciones_oaf(hc, filas) -> None:
    """Reemplaza las mediciones de monitoreo de un paciente.

    `filas` es una lista de dicts {'orden', 'tiempo', 'fc', 'fr', 'sato2',
    'score_tal', 'fio2', 'flujo'} (una por tiempo). Solo se guardan las filas
    con al menos un valor cargado. Si no vino ninguna con datos, no se toca lo
    existente (para no borrarlo desde vistas que no editan la tabla).
    """
    db = get_db()
    hc = (hc or "").strip()
    params = ("fc", "fr", "sato2", "score_tal", "fio2", "flujo")
    con_datos = [f for f in filas if any((f.get(p) or "").strip() for p in params)]
    if not con_datos:
        return

    db.execute("DELETE FROM mediciones_oaf WHERE hc = ?", (hc,))
    for f in con_datos:
        db.execute(
            "INSERT INTO mediciones_oaf "
            "(hc, orden, tiempo, fc, fr, sato2, score_tal, fio2, flujo) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (hc, f.get("orden"), f.get("tiempo"), f.get("fc"), f.get("fr"),
             f.get("sato2"), f.get("score_tal"), f.get("fio2"), f.get("flujo")),
        )
    db.commit()


def log_historial(hc: str, campo: str, valor_anterior: str,
                   valor_nuevo: str, fecha: str) -> None:
    db = get_db()
    db.execute("""
        INSERT INTO historial (hc, campo, valor_anterior, valor_nuevo, fecha)
        VALUES (?, ?, ?, ?, ?)
    """, (hc, campo, valor_anterior, valor_nuevo, fecha))
    db.commit()


def get_historial_paciente(hc: str):
    return get_db().execute("""
        SELECT * FROM historial WHERE hc = ? ORDER BY fecha ASC
    """, (hc,)).fetchall()


def get_atenciones_paciente(hc: str):
    return get_db().execute("""
        SELECT * FROM atenciones_diarias WHERE hc = ? ORDER BY fecha ASC
    """, (hc,)).fetchall()


def dar_alta(hc: str, fecha_alta: str) -> None:
    db = get_db()
    db.execute(
        "UPDATE pacientes SET estado='ALTA', fecha_alta=? WHERE hc=?",
        (fecha_alta, hc),
    )
    db.commit()


def borrar_paciente(hc: str) -> None:
    """Borra un paciente y TODOS sus datos asociados de forma permanente.

    Elimina de las tres tablas ligadas por hc (historial, atenciones_diarias
    y pacientes) dentro de una sola transacción: o se borra todo o no se borra
    nada. No tiene deshacer. Solo debe llamarse desde una ruta protegida por
    requiere_admin.
    """
    db = get_db()
    hc = (hc or "").strip()
    db.execute("DELETE FROM historial WHERE hc = ?", (hc,))
    db.execute("DELETE FROM atenciones_diarias WHERE hc = ?", (hc,))
    db.execute("DELETE FROM pacientes WHERE hc = ?", (hc,))
    db.commit()


def get_inactivos(dias: int = 3):
    cutoff = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")
    return get_db().execute("""
        SELECT p.hc, p.nombre, p.soporte, p.sala,
               p.tq, MAX(a.fecha) AS ultima_atencion
        FROM pacientes p
        LEFT JOIN atenciones_diarias a ON p.hc = a.hc
        WHERE p.estado = 'ACTIVO'
        GROUP BY p.hc
        HAVING MAX(a.fecha) IS NULL OR MAX(a.fecha) < ?
        ORDER BY ultima_atencion ASC
    """, (cutoff,)).fetchall()


def buscar_pacientes(query: str):
    q = f"%{query}%"
    return get_db().execute("""
        SELECT *
        FROM pacientes
        WHERE hc LIKE ? OR nombre LIKE ?
        ORDER BY ultima_actualizacion DESC
    """, (q, q)).fetchall()


def get_deduplicacion_pendiente():
    # La tabla deduplicacion_pacientes solo existe en bases SQLite legacy con
    # HC duplicadas. Si no existe (ej: Postgres nuevo), devolvemos lista vacía.
    db = get_db()
    try:
        return db.execute("""
            SELECT * FROM deduplicacion_pacientes
            WHERE estado = 'PENDIENTE'
            ORDER BY detectado_en DESC
        """).fetchall()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return []


def get_historial_exportar():
    return get_db().execute("""
        SELECT a.fecha, a.hc, p.nombre, p.edad, p.diagnostico,
               p.soporte, CASE WHEN p.tq = 1 THEN 'SI' ELSE 'NO' END AS tq,
               p.sala, p.muestra, a.atenciones
        FROM atenciones_diarias a
        JOIN pacientes p ON a.hc = p.hc
        ORDER BY a.fecha DESC, a.hc
    """).fetchall()


def get_export_agrupado():
    """Devuelve los datos para exportar AGRUPADOS por paciente.

    Estructura:
        [
          {
            "paciente": <row de pacientes>,
            "atenciones": [{"fecha", "soporte", "sala", "atenciones"}, ...],  # dia por dia
            "total": <suma de atenciones>,
          },
          ...
        ]

    Para cada día se calcula el soporte y la sala que estaban vigentes en esa
    fecha (según el historial), no el valor actual del paciente.
    """
    from oafcare.utils.soporte import soporte_en_fecha

    db = get_db()
    pacientes = db.execute("""
        SELECT p.hc, p.nombre, p.edad, p.diagnostico, p.soporte,
               p.sala, p.tq, p.muestra, p.estado
        FROM pacientes p
        WHERE EXISTS (SELECT 1 FROM atenciones_diarias a WHERE a.hc = p.hc)
        ORDER BY LOWER(p.nombre), p.hc
    """).fetchall()

    resultado = []
    for p in pacientes:
        hc = p["hc"]
        atenciones = db.execute(
            "SELECT fecha, atenciones FROM atenciones_diarias WHERE hc=? ORDER BY fecha ASC, id ASC",
            (hc,),
        ).fetchall()
        historial = db.execute("""
            SELECT campo, valor_nuevo, fecha
            FROM historial
            WHERE hc=? AND campo IN ('soporte', 'sala')
            ORDER BY fecha ASC
        """, (hc,)).fetchall()

        eventos_soporte = [
            {"fecha": r["fecha"][:10], "valor_nuevo": r["valor_nuevo"]}
            for r in historial if r["campo"] == "soporte"
        ]
        eventos_sala = [
            {"fecha": r["fecha"][:10], "valor_nuevo": r["valor_nuevo"]}
            for r in historial if r["campo"] == "sala"
        ]

        filas = []
        total = 0
        for a in atenciones:
            fecha = a["fecha"]
            cant = a["atenciones"] or 0
            try:
                total += int(cant)
            except (ValueError, TypeError):
                pass
            filas.append({
                "fecha": fecha,
                "soporte": soporte_en_fecha(eventos_soporte, fecha, p["soporte"] or ""),
                "sala": soporte_en_fecha(eventos_sala, fecha, p["sala"] or ""),
                "atenciones": cant,
            })

        resultado.append({"paciente": p, "atenciones": filas, "total": total})

    return resultado

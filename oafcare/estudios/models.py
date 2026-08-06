"""Acceso a la tabla `estudios` (las investigaciones del repositorio).

El SQL se arma desde ESTUDIO_COLUMNAS, así que sumar un campo al formulario no
requiere tocar este archivo: alcanza con agregarlo a esa lista en
utils/estudio.py.
"""

from datetime import datetime

from oafcare.database import get_db
from oafcare.utils.estudio import ESTUDIO_COLUMNAS


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def crear_estudio(datos: dict, usuario: str) -> None:
    """Inserta una investigación nueva.

    `datos` es lo que devuelve `estudio_desde_form` (claves = ESTUDIO_COLUMNAS).
    No devuelve el id: obtenerlo sería distinto en SQLite (lastrowid) y en
    Postgres (RETURNING), y ningún flujo lo necesita — después de guardar se va
    al listado del repositorio.
    """
    cols = list(ESTUDIO_COLUMNAS) + ["creado_por", "creado_en", "actualizado_en"]
    ahora = _ahora()
    valores = [datos.get(c, "") for c in ESTUDIO_COLUMNAS] + [usuario, ahora, ahora]
    placeholders = ", ".join(["?"] * len(cols))

    db = get_db()
    db.execute(
        f"INSERT INTO estudios ({', '.join(cols)}) VALUES ({placeholders})",
        valores,
    )
    db.commit()


def actualizar_estudio(estudio_id: int, datos: dict) -> None:
    """Sobrescribe los campos del formulario de una investigación existente.

    Todas las columnas del formulario se escriben (no hay COALESCE): el form
    manda siempre el conjunto completo, y un campo borrado a propósito tiene que
    quedar vacío.
    """
    asignaciones = ", ".join(f"{c}=?" for c in ESTUDIO_COLUMNAS)
    valores = [datos.get(c, "") for c in ESTUDIO_COLUMNAS] + [_ahora(), estudio_id]

    db = get_db()
    db.execute(
        f"UPDATE estudios SET {asignaciones}, actualizado_en=? WHERE id=?",
        valores,
    )
    db.commit()


def get_estudio(estudio_id: int):
    return get_db().execute(
        "SELECT * FROM estudios WHERE id = ?", (estudio_id,)
    ).fetchone()


def get_todos_estudios():
    """Todas las investigaciones cargadas, la más reciente primero."""
    return get_db().execute(
        "SELECT * FROM estudios ORDER BY creado_en DESC, id DESC"
    ).fetchall()


def buscar_estudios_por_titulo(titulo: str):
    """Busca investigaciones por título, sin importar mayúsculas.

    `LOWER()` en los dos lados para que se comporte igual en SQLite y Postgres.
    """
    q = f"%{(titulo or '').strip().lower()}%"
    return get_db().execute("""
        SELECT *
        FROM estudios
        WHERE LOWER(titulo) LIKE ?
        ORDER BY LOWER(titulo), id
    """, (q,)).fetchall()


def borrar_estudio(estudio_id: int) -> None:
    """Borra una investigación. Solo desde una ruta protegida por requiere_admin."""
    db = get_db()
    db.execute("DELETE FROM estudios WHERE id = ?", (estudio_id,))
    db.commit()

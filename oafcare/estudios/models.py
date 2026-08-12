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


# Una investigación archivada sigue en la tabla, pero con fecha en
# `archivado_en`. Este trozo de SQL es el que la deja afuera de todo lo que se
# consulta normalmente (repositorio y búsqueda por título). Se compara contra
# NULL Y contra '' porque las columnas migradas quedan en NULL y las nuevas
# pueden guardarse como cadena vacía; así funciona igual en SQLite y Postgres.
SOLO_ACTIVAS = "(archivado_en IS NULL OR archivado_en = '')"
SOLO_ARCHIVADAS = "(archivado_en IS NOT NULL AND archivado_en <> '')"


def esta_archivada(estudio) -> bool:
    """True si la investigación fue archivada (sacada del repositorio)."""
    if not estudio:
        return False
    return bool((estudio["archivado_en"] or "").strip())


def crear_estudio(datos: dict, nombre: str, dni: str) -> None:
    """Inserta una investigación nueva a nombre de quien la carga.

    `datos` es lo que devuelve `estudio_desde_form` (claves = ESTUDIO_COLUMNAS).
    `nombre` se guarda para mostrar y `dni` es la identidad: es lo que después
    compara `puede_modificar` para dejar editar el registro.

    No devuelve el id: obtenerlo sería distinto en SQLite (lastrowid) y en
    Postgres (RETURNING), y ningún flujo lo necesita — después de guardar se va
    al listado del repositorio.
    """
    cols = list(ESTUDIO_COLUMNAS) + [
        "creado_por", "creado_por_dni", "creado_en", "actualizado_en",
    ]
    ahora = _ahora()
    valores = (
        [datos.get(c, "") for c in ESTUDIO_COLUMNAS]
        + [nombre, dni, ahora, ahora]
    )
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
    """Las investigaciones activas, la más reciente primero.

    Las archivadas quedan afuera: viven en `get_estudios_archivados()`, que solo
    mira un admin.
    """
    return get_db().execute(
        f"SELECT * FROM estudios WHERE {SOLO_ACTIVAS} "
        "ORDER BY creado_en DESC, id DESC"
    ).fetchall()


def get_estudios_archivados():
    """Las investigaciones archivadas, la archivada hace menos tiempo primero."""
    return get_db().execute(
        f"SELECT * FROM estudios WHERE {SOLO_ARCHIVADAS} "
        "ORDER BY archivado_en DESC, id DESC"
    ).fetchall()


def buscar_estudios_por_titulo(titulo: str):
    """Busca investigaciones ACTIVAS por título, sin importar mayúsculas.

    `LOWER()` en los dos lados para que se comporte igual en SQLite y Postgres.
    Las archivadas no aparecen: para quien busca, dejaron de existir.
    """
    q = f"%{(titulo or '').strip().lower()}%"
    return get_db().execute(f"""
        SELECT *
        FROM estudios
        WHERE LOWER(titulo) LIKE ? AND {SOLO_ACTIVAS}
        ORDER BY LOWER(titulo), id
    """, (q,)).fetchall()


def puede_modificar(estudio, usuario) -> bool:
    """True si `usuario` es quien cargó `estudio`.

    Se compara por DNI, no por nombre: el nombre puede repetirse o estar
    escrito distinto. Una investigación sin `creado_por_dni` (cargada antes de
    que existiera el ingreso por DNI) no tiene dueño identificable y por lo
    tanto no se puede modificar.

    Una investigación ARCHIVADA tampoco se modifica, ni siquiera por su autor:
    salió del repositorio y lo único que le puede pasar es que un admin la
    restaure. El chequeo va acá, que es por donde pasan las rutas de edición y
    los botones de las vistas.
    """
    if not estudio or not usuario or not getattr(usuario, "dni", ""):
        return False
    if esta_archivada(estudio):
        return False
    return (estudio["creado_por_dni"] or "").strip() == usuario.dni


def archivar_estudio(estudio_id: int, nombre: str) -> None:
    """Saca una investigación del repositorio sin borrarla.

    Deja de aparecer en el repositorio, en la búsqueda por título y en la ficha
    para quien no sea admin, pero la fila queda intacta: `restaurar_estudio` la
    devuelve tal cual estaba. Solo desde una ruta con requiere_admin.
    """
    db = get_db()
    db.execute(
        "UPDATE estudios SET archivado_en=?, archivado_por=? WHERE id=?",
        (_ahora(), nombre, estudio_id),
    )
    db.commit()


def restaurar_estudio(estudio_id: int) -> None:
    """Devuelve al repositorio una investigación archivada."""
    db = get_db()
    db.execute(
        "UPDATE estudios SET archivado_en='', archivado_por='' WHERE id=?",
        (estudio_id,),
    )
    db.commit()


def borrar_estudio(estudio_id: int) -> None:
    """Borra la fila para siempre. Esto no tiene vuelta atrás.

    Solo desde una ruta protegida por requiere_admin, y solo sobre una
    investigación YA archivada: el borrado es el segundo paso deliberado, nunca
    un clic desde el repositorio (ver `estudios.borrar`).
    """
    db = get_db()
    db.execute("DELETE FROM estudios WHERE id = ?", (estudio_id,))
    db.commit()

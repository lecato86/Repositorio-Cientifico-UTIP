"""Acceso a la base y creación del esquema.

La app tiene UNA sola tabla: `estudios`, las investigaciones del repositorio.
Las tablas que venían de OAFCare (pacientes, atenciones_diarias, historial,
mediciones_oaf, usuarios) se eliminaron; ver `_borrar_tablas_oafcare()`.

Soporta dos motores: Postgres si hay DATABASE_URL (producción), SQLite si no
(desarrollo local).
"""

import sqlite3
from flask import g, current_app

from .utils.estudio import ESTUDIO_COLUMNAS

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # psycopg solo hace falta en producción (Postgres)
    psycopg = None
    dict_row = None


# La lista canónica de columnas de `estudios` (ESTUDIO_COLUMNAS) vive en
# utils/estudio.py, junto a las opciones del formulario y los parsers. Acá se
# usa para armar el CREATE TABLE y las migraciones, y así no queda duplicada.
# Todas TEXT: admiten vacío y texto libre.

# Columnas de `estudios` que NO son del formulario: quién la cargó y cuándo.
# `creado_por` es el nombre para mostrar y `creado_por_dni` la identidad real:
# es la que se compara para decidir si alguien puede modificar el registro.
ESTUDIO_COLUMNAS_META = [
    "creado_por",
    "creado_por_dni",
    "creado_en",
    "actualizado_en",
]

# Tablas de OAFCare (seguimiento de pacientes en OAF). El proyecto derivaba de
# ahí; ese dominio se eliminó por completo y estas tablas se borran de las
# bases que todavía las tengan. `pacientes_old` era el intermedio de una
# migración vieja. `usuarios` también se va: el ingreso es por nombre + DNI y
# no persiste nada (ver oafcare/auth/models.py).
TABLAS_OAFCARE = [
    "mediciones_oaf",
    "atenciones_diarias",
    "historial",
    "deduplicacion_pacientes",
    "pacientes_old",
    "pacientes",
    "usuarios",
]


def _estudios_columnas_sql(indent: str = "                ") -> str:
    """'titulo TEXT, tema TEXT, ...' para el CREATE TABLE de `estudios`."""
    return (",\n" + indent).join(f"{col} TEXT" for col in ESTUDIO_COLUMNAS)


# ---------------------------------------------------------------------------
# Selección de motor
# ---------------------------------------------------------------------------
# Si en la config hay DATABASE_URL -> Postgres (producción, ej: Neon en Render).
# Si no -> SQLite (archivo local, para desarrollo).

def _usa_postgres() -> bool:
    return bool(current_app.config.get("DATABASE_URL"))


# ---------------------------------------------------------------------------
# Envoltorios para que el código de la app sea igual en SQLite y Postgres
# ---------------------------------------------------------------------------
# SQLite usa placeholders '?' y sqlite3.Row (acceso por nombre y por índice).
# psycopg usa '%s' y devuelve dicts. Estos wrappers traducen '?'->'%s' y hacen
# que las filas se puedan leer tanto por row["col"] como por row[0].

class _PgRow:
    __slots__ = ("_d",)

    def __init__(self, d):
        self._d = d

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._d.values())[key]
        return self._d[key]

    def __iter__(self):
        return iter(self._d.values())

    def keys(self):
        return list(self._d.keys())

    def get(self, key, default=None):
        return self._d.get(key, default)


class _PgCursor:
    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql, params=()):
        self._cur.execute(sql.replace("?", "%s"), params)
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        return _PgRow(row) if row is not None else None

    def fetchall(self):
        return [_PgRow(r) for r in self._cur.fetchall()]

    def fetchmany(self, size):
        return [_PgRow(r) for r in self._cur.fetchmany(size)]

    def __iter__(self):
        return iter(self.fetchall())


class _PgConn:
    """Imita la interfaz mínima de sqlite3.Connection que usa la app."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        return _PgCursor(self._conn.cursor()).execute(sql, params)

    def cursor(self):
        return _PgCursor(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


# ---------------------------------------------------------------------------
# Conexión por request
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        if _usa_postgres():
            if psycopg is None:
                raise RuntimeError(
                    "DATABASE_URL está seteada pero psycopg no está instalado. "
                    "Agregá 'psycopg[binary]' a requirements.txt."
                )
            conn = psycopg.connect(
                current_app.config["DATABASE_URL"], row_factory=dict_row
            )
            g.db = _PgConn(conn)
        else:
            g.db = sqlite3.connect(
                current_app.config["DATABASE"],
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ---------------------------------------------------------------------------
# Inicialización de esquema
# ---------------------------------------------------------------------------

def init_db() -> None:
    if _usa_postgres():
        _init_postgres()
    else:
        _init_sqlite()


# ============================ POSTGRES ============================

def _init_postgres() -> None:
    conn = psycopg.connect(current_app.config["DATABASE_URL"])
    try:
        with conn.cursor() as c:
            # Investigaciones del repositorio científico: la única tabla.
            c.execute(f"""CREATE TABLE IF NOT EXISTS estudios (
                id SERIAL PRIMARY KEY,
                {_estudios_columnas_sql()},
                creado_por TEXT,
                creado_por_dni TEXT,
                creado_en TEXT,
                actualizado_en TEXT
            )""")

            # Bases ya existentes: agregar las columnas que falten.
            for col in ESTUDIO_COLUMNAS + ESTUDIO_COLUMNAS_META:
                c.execute(
                    f"ALTER TABLE estudios ADD COLUMN IF NOT EXISTS {col} TEXT"
                )

            _borrar_tablas_oafcare(c)
        conn.commit()
    finally:
        conn.close()


# ============================ SQLITE ============================

def _init_sqlite() -> None:
    conn = sqlite3.connect(current_app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Investigaciones del repositorio científico: la única tabla.
    c.execute(f"""CREATE TABLE IF NOT EXISTS estudios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        {_estudios_columnas_sql(indent="        ")},
        creado_por TEXT,
        creado_por_dni TEXT,
        creado_en TEXT,
        actualizado_en TEXT
    )""")
    conn.commit()

    # Bases ya existentes: agregar las columnas que falten.
    for col in ESTUDIO_COLUMNAS + ESTUDIO_COLUMNAS_META:
        _add_column_if_missing(conn, "estudios", col, "TEXT")

    _borrar_tablas_oafcare(c)
    conn.commit()
    conn.close()


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str,
                           definition: str) -> None:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if not any(col[1] == column for col in cols):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.commit()


# ============================ COMÚN ============================

def _borrar_tablas_oafcare(cursor) -> None:
    """Elimina las tablas heredadas de OAFCare de bases que todavía las tengan.

    El dominio de pacientes se sacó del proyecto entero; estas tablas quedarían
    huérfanas. `DROP TABLE IF EXISTS` es idempotente, así que correrlo en cada
    arranque no cuesta nada y alcanza a la base de producción sin intervención
    manual. Se puede quitar cuando no queden bases viejas dando vueltas.

    El `cursor` tiene que ser el crudo del motor (no `get_db()`): esto corre
    dentro de init_db(), fuera de un request.
    """
    for tabla in TABLAS_OAFCARE:
        cursor.execute(f"DROP TABLE IF EXISTS {tabla}")

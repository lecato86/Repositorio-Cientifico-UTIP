import sqlite3
from flask import g, current_app
from werkzeug.security import generate_password_hash

from .utils.estudio import ESTUDIO_COLUMNAS

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # psycopg solo hace falta en producción (Postgres)
    psycopg = None
    dict_row = None


# Columnas del formulario de ingreso que se agregaron después del esquema
# original. Todas TEXT (permiten vacío y valores libres). Se crean en el
# CREATE TABLE de bases nuevas y se agregan por migración a bases viejas.
# Mantener sincronizado con oafcare/utils/ingreso.py.
PACIENTE_COLUMNAS_INGRESO = [
    "sexo",
    "peso",
    "fecha_inicio_oaf",
    "sala_derivacion",
    "virus_vsr",
    "virus_adenovirus",
    "virus_influenza",
    "virus_parainfluenza",
    "virus_metapneumovirus",
    "virus_sarscov2",
    "virus_picornavirus",
    "virus_otros",
    "virus_otro_detalle",
    "comorbilidades",
    "hora_inicio_oaf",
    "soporte_previo_oaf",
    "lugar_inicio_oaf",
    "fecha_inicio_alimentacion",
    "complicaciones",
    "fecha_fin_oaf",
    "hora_fin_oaf",
    "resultado_oaf",
]


# La lista canónica de columnas de `estudios` (ESTUDIO_COLUMNAS) vive en
# utils/estudio.py, junto a las opciones del formulario y los parsers. Acá se
# usa para armar el CREATE TABLE y las migraciones, y así no queda duplicada.
# Todas TEXT: admiten vacío y texto libre.

def _estudios_columnas_sql() -> str:
    """'titulo TEXT, tema TEXT, ...' para el CREATE TABLE de `estudios`."""
    return ",\n                ".join(f"{col} TEXT" for col in ESTUDIO_COLUMNAS)


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
            c.execute("""CREATE TABLE IF NOT EXISTS pacientes (
                hc TEXT PRIMARY KEY,
                nombre TEXT,
                edad INTEGER,
                diagnostico TEXT,
                soporte TEXT,
                sala TEXT,
                ultima_actualizacion TEXT,
                estado TEXT DEFAULT 'ACTIVO',
                fecha_alta TEXT,
                muestra TEXT,
                tq INTEGER DEFAULT 0,
                sexo TEXT,
                peso TEXT,
                fecha_inicio_oaf TEXT,
                sala_derivacion TEXT,
                virus_vsr TEXT,
                virus_adenovirus TEXT,
                virus_influenza TEXT,
                virus_parainfluenza TEXT,
                virus_metapneumovirus TEXT,
                virus_sarscov2 TEXT,
                virus_picornavirus TEXT,
                virus_otros TEXT,
                virus_otro_detalle TEXT,
                comorbilidades TEXT,
                hora_inicio_oaf TEXT,
                soporte_previo_oaf TEXT,
                lugar_inicio_oaf TEXT,
                fecha_inicio_alimentacion TEXT,
                complicaciones TEXT,
                fecha_fin_oaf TEXT,
                hora_fin_oaf TEXT,
                resultado_oaf TEXT
            )""")

            # Bases Postgres ya existentes: agregar las columnas de ingreso
            # si faltan (idempotente).
            for col in PACIENTE_COLUMNAS_INGRESO:
                c.execute(
                    f"ALTER TABLE pacientes ADD COLUMN IF NOT EXISTS {col} TEXT"
                )

            # Normalización: 'Servicio de Emergencias' pasó a llamarse
            # 'Guardia Central'. Idempotente.
            c.execute(
                "UPDATE pacientes SET lugar_inicio_oaf = 'Guardia Central' "
                "WHERE lugar_inicio_oaf = 'Servicio de Emergencias'"
            )
            # Normalización: 'GUARDIA CENTRAL' pasó a escribirse 'Guardia
            # Central' en la sala de derivación. Idempotente.
            c.execute(
                "UPDATE pacientes SET sala_derivacion = 'Guardia Central' "
                "WHERE sala_derivacion = 'GUARDIA CENTRAL'"
            )
            # Normalización: la sala 'UTII' pasó a llamarse 'UTI'. Idempotente.
            c.execute(
                "UPDATE pacientes SET sala_derivacion = 'UTI' "
                "WHERE sala_derivacion = 'UTII'"
            )

            c.execute("""CREATE TABLE IF NOT EXISTS mediciones_oaf (
                id SERIAL PRIMARY KEY,
                hc TEXT,
                orden INTEGER,
                tiempo TEXT,
                fc TEXT,
                fr TEXT,
                sato2 TEXT,
                score_tal TEXT,
                fio2 TEXT,
                flujo TEXT
            )""")

            c.execute("""CREATE TABLE IF NOT EXISTS atenciones_diarias (
                id SERIAL PRIMARY KEY,
                hc TEXT,
                fecha TEXT,
                atenciones INTEGER
            )""")

            c.execute("""CREATE TABLE IF NOT EXISTS historial (
                id SERIAL PRIMARY KEY,
                hc TEXT,
                campo TEXT,
                valor_anterior TEXT,
                valor_nuevo TEXT,
                fecha TEXT
            )""")

            c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                rol TEXT NOT NULL DEFAULT 'lector'
            )""")

            # Investigaciones del repositorio científico. Independiente de las
            # tablas de OAF: acá va lo que se carga por apartados desde
            # "Cargar nueva investigación".
            c.execute(f"""CREATE TABLE IF NOT EXISTS estudios (
                id SERIAL PRIMARY KEY,
                {_estudios_columnas_sql()},
                creado_por TEXT,
                creado_en TEXT,
                actualizado_en TEXT
            )""")

            # Bases ya existentes: agregar los campos de apartados que falten.
            for col in ESTUDIO_COLUMNAS:
                c.execute(
                    f"ALTER TABLE estudios ADD COLUMN IF NOT EXISTS {col} TEXT"
                )

            c.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_pacientes_hc_trim "
                "ON pacientes ((TRIM(hc)))"
            )
        conn.commit()
        _seed_usuarios(conn, placeholder="%s")
    finally:
        conn.close()


# ============================ SQLITE ============================

def _init_sqlite() -> None:
    db_path = current_app.config["DATABASE"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS pacientes (
        hc TEXT PRIMARY KEY,
        nombre TEXT,
        edad INTEGER,
        diagnostico TEXT,
        soporte TEXT,
        sala TEXT,
        ultima_actualizacion TEXT,
        estado TEXT DEFAULT 'ACTIVO',
        fecha_alta TEXT,
        muestra TEXT,
        tq INTEGER DEFAULT 0,
        sexo TEXT,
        peso TEXT,
        fecha_inicio_oaf TEXT,
        sala_derivacion TEXT,
        virus_vsr TEXT,
        virus_adenovirus TEXT,
        virus_influenza TEXT,
        virus_parainfluenza TEXT,
        virus_metapneumovirus TEXT,
        virus_sarscov2 TEXT,
        virus_picornavirus TEXT,
        virus_otros TEXT,
        virus_otro_detalle TEXT,
        comorbilidades TEXT,
        hora_inicio_oaf TEXT,
        soporte_previo_oaf TEXT,
        lugar_inicio_oaf TEXT,
        fecha_inicio_alimentacion TEXT,
        complicaciones TEXT,
        fecha_fin_oaf TEXT,
        hora_fin_oaf TEXT,
        resultado_oaf TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS mediciones_oaf (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hc TEXT,
        orden INTEGER,
        tiempo TEXT,
        fc TEXT,
        fr TEXT,
        sato2 TEXT,
        score_tal TEXT,
        fio2 TEXT,
        flujo TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS atenciones_diarias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hc TEXT,
        fecha TEXT,
        atenciones INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS historial (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hc TEXT,
        campo TEXT,
        valor_anterior TEXT,
        valor_nuevo TEXT,
        fecha TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        rol TEXT NOT NULL DEFAULT 'lector'
    )""")

    # Investigaciones del repositorio científico (ver el equivalente Postgres).
    c.execute(f"""CREATE TABLE IF NOT EXISTS estudios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        {_estudios_columnas_sql()},
        creado_por TEXT,
        creado_en TEXT,
        actualizado_en TEXT
    )""")

    conn.commit()
    # Bases ya existentes: agregar los campos de apartados que falten.
    for col in ESTUDIO_COLUMNAS:
        _add_column_if_missing(conn, "estudios", col, "TEXT")
    _recuperar_migracion_incompleta(conn)
    _add_column_if_missing(conn, "pacientes", "tq", "INTEGER DEFAULT 0")
    _migrate_edad_to_integer(conn)
    _migrate_hc_uniqueness(conn)
    # Después de _migrate_edad_to_integer, que recrea la tabla en bases legacy:
    # así las columnas de ingreso no se pierden en esa recreación.
    for col in PACIENTE_COLUMNAS_INGRESO:
        _add_column_if_missing(conn, "pacientes", col, "TEXT")
    # Normalización: 'Servicio de Emergencias' -> 'Guardia Central' (idempotente).
    conn.execute(
        "UPDATE pacientes SET lugar_inicio_oaf = 'Guardia Central' "
        "WHERE lugar_inicio_oaf = 'Servicio de Emergencias'"
    )
    # Normalización: 'GUARDIA CENTRAL' -> 'Guardia Central' en sala de
    # derivación (idempotente).
    conn.execute(
        "UPDATE pacientes SET sala_derivacion = 'Guardia Central' "
        "WHERE sala_derivacion = 'GUARDIA CENTRAL'"
    )
    # Normalización: 'UTII' -> 'UTI' en sala de derivación (idempotente).
    conn.execute(
        "UPDATE pacientes SET sala_derivacion = 'UTI' "
        "WHERE sala_derivacion = 'UTII'"
    )
    conn.commit()
    _seed_usuarios(conn)
    conn.close()


def _recuperar_migracion_incompleta(conn: sqlite3.Connection) -> None:
    """Recupera datos si una migración anterior crasheó a mitad de camino.

    _migrate_edad_to_integer renombra `pacientes` -> `pacientes_old` y luego
    recrea `pacientes`. Si la app se cae entre medio, al reiniciar el
    CREATE TABLE IF NOT EXISTS crea una tabla `pacientes` vacía y los datos
    quedan atrapados en `pacientes_old`. Acá lo detectamos y restauramos.
    """
    tiene_old = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='pacientes_old'"
    ).fetchone()
    if not tiene_old:
        return

    pacientes_vacia = conn.execute("SELECT COUNT(*) FROM pacientes").fetchone()[0] == 0
    old_con_datos = conn.execute("SELECT COUNT(*) FROM pacientes_old").fetchone()[0] > 0

    if pacientes_vacia and old_con_datos:
        cols_old = {c[1] for c in conn.execute("PRAGMA table_info(pacientes_old)")}
        cols_new = [c[1] for c in conn.execute("PRAGMA table_info(pacientes)")]
        comunes = [c for c in cols_new if c in cols_old]
        lista = ", ".join(comunes)
        conn.execute(f"INSERT INTO pacientes ({lista}) SELECT {lista} FROM pacientes_old")
        conn.commit()

    conn.execute("DROP TABLE IF EXISTS pacientes_old")
    conn.commit()


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if not any(col[1] == column for col in cols):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.commit()


def _migrate_edad_to_integer(conn: sqlite3.Connection) -> None:
    c = conn.cursor()
    c.execute("PRAGMA table_info(pacientes)")
    cols = c.fetchall()
    edad_col = next((col for col in cols if col[1] == "edad"), None)
    if edad_col and edad_col[2].upper() != "INTEGER":
        from oafcare.utils.edad import parse_edad_meses
        try:
            c.execute("ALTER TABLE pacientes ADD COLUMN edad_int INTEGER")
            rows = c.execute("SELECT hc, edad FROM pacientes").fetchall()
            for row in rows:
                total = parse_edad_meses(row[1], asumir_anios_legacy=True)
                c.execute("UPDATE pacientes SET edad_int=? WHERE hc=?", (total, row[0]))
            c.execute("ALTER TABLE pacientes RENAME TO pacientes_old")
            c.execute("""CREATE TABLE pacientes (
                hc TEXT PRIMARY KEY, nombre TEXT, edad INTEGER,
                diagnostico TEXT, soporte TEXT, sala TEXT,
                ultima_actualizacion TEXT, estado TEXT DEFAULT 'ACTIVO',
                fecha_alta TEXT, muestra TEXT, tq INTEGER DEFAULT 0
            )""")
            c.execute("""INSERT INTO pacientes
                SELECT hc, nombre, edad_int, diagnostico, soporte, sala,
                       ultima_actualizacion, estado, fecha_alta, muestra, COALESCE(tq, 0)
                FROM pacientes_old""")
            c.execute("DROP TABLE pacientes_old")
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _migrate_hc_uniqueness(conn: sqlite3.Connection) -> None:
    c = conn.cursor()
    duplicates = c.execute("""
        SELECT TRIM(hc) AS hc_normalizado, COUNT(*) AS cantidad
        FROM pacientes
        GROUP BY TRIM(hc)
        HAVING COUNT(*) > 1
    """).fetchall()

    if duplicates:
        c.execute("""CREATE TABLE IF NOT EXISTS deduplicacion_pacientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hc_normalizado TEXT,
            cantidad INTEGER,
            detectado_en TEXT,
            estado TEXT DEFAULT 'PENDIENTE'
        )""")
        c.execute("DELETE FROM deduplicacion_pacientes WHERE estado = 'PENDIENTE'")
        for row in duplicates:
            c.execute("""
                INSERT INTO deduplicacion_pacientes (hc_normalizado, cantidad, detectado_en)
                VALUES (?, ?, datetime('now'))
            """, (row[0], row[1]))
        conn.commit()
        return

    c.execute("UPDATE pacientes SET hc = TRIM(hc)")
    c.execute("UPDATE atenciones_diarias SET hc = TRIM(hc)")
    c.execute("UPDATE historial SET hc = TRIM(hc)")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_pacientes_hc_trim ON pacientes(TRIM(hc))")
    conn.commit()


# ============================ COMÚN ============================

def _seed_usuarios(conn, placeholder: str = "?") -> None:
    """Crea los usuarios iniciales si la tabla está vacía.

    Los usuarios/contraseñas NO están hardcodeados: vienen de la variable
    de entorno SEED_USERS, parseada en Config.SEED_USUARIOS.
    Sirve para SQLite (placeholder '?') y para el conn crudo de psycopg ('%s').
    """
    usuarios = current_app.config.get("SEED_USUARIOS") or []
    if not usuarios:
        return

    count = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    if count == 0:
        sql = (
            f"INSERT INTO usuarios (username, password_hash, rol) "
            f"VALUES ({placeholder}, {placeholder}, {placeholder}) "
            f"ON CONFLICT (username) DO NOTHING"
        )
        for username, password, rol in usuarios:
            conn.execute(sql, (username, generate_password_hash(password), rol))
        conn.commit()

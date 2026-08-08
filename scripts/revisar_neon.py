"""Revisa el estado de la base de PRODUCCIÓN (Neon) sin modificar nada.

Solo lee: informa qué tablas hay, qué columnas tiene `estudios`, cuántas
investigaciones están cargadas y quién las cargó. Sirve para confirmar que lo
que se carga desde la app publicada está llegando a la base de verdad.

Uso:
    python scripts/revisar_neon.py

Toma la conexión de BACKUP_DATABASE_URL y, si no está, de DATABASE_URL (ambas
del .env, que nunca se commitea). Si no hay ninguna, avisa y no hace nada.

NO escribe: no crea tablas, no borra, no inserta.
"""
import os
import sys

# Permite ejecutar el script desde cualquier carpeta.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from oafcare.database import ESTUDIO_COLUMNAS_META, TABLAS_OAFCARE
from oafcare.utils.estudio import ESTUDIO_COLUMNAS


def main() -> None:
    url = Config.BACKUP_DATABASE_URL or Config.DATABASE_URL
    if not url:
        raise SystemExit(
            "No hay conexión a Postgres configurada.\n\n"
            "Agregá al archivo .env (que nunca se commitea) la línea:\n"
            "  BACKUP_DATABASE_URL=postgresql://usuario:password@host/base?sslmode=require\n\n"
            "Es la connection string que da Neon en su panel."
        )

    import psycopg

    # Se muestra el host para saber contra qué base se está mirando, sin
    # exponer usuario ni contraseña.
    host = url.split("@")[-1].split("/")[0] if "@" in url else "?"
    print(f"Base: {host}\n")

    with psycopg.connect(url) as conn:
        with conn.cursor() as c:
            c.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' ORDER BY table_name
            """)
            tablas = [r[0] for r in c.fetchall()]
            print("TABLAS")
            for t in tablas:
                print(f"   {t}")
            if not tablas:
                print("   (ninguna: la app todavía no arrancó contra esta base)")
                return

            quedan = [t for t in TABLAS_OAFCARE if t in tablas]
            print()
            print("   Tablas viejas de OAFCare:",
                  ", ".join(quedan) if quedan else "ninguna (borradas, como corresponde)")

            if "estudios" not in tablas:
                print("\nNo existe la tabla `estudios`: la app no llegó a crearla.")
                return

            c.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'estudios'
            """)
            columnas = {r[0] for r in c.fetchall()}
            esperadas = list(ESTUDIO_COLUMNAS) + list(ESTUDIO_COLUMNAS_META)
            faltan = [col for col in esperadas if col not in columnas]

            print()
            print(f"COLUMNAS DE `estudios`: {len(columnas)}")
            print("   faltantes:", ", ".join(faltan) if faltan else "ninguna")

            c.execute("SELECT COUNT(*) FROM estudios")
            total = c.fetchone()[0]
            print()
            print(f"INVESTIGACIONES CARGADAS: {total}")

            if not total:
                print("   La tabla existe pero está vacía: todavía no se guardó nada.")
                return

            c.execute("""
                SELECT id, titulo, estado_actual, creado_por, creado_por_dni,
                       telefono_contacto, email_contacto, creado_en
                FROM estudios ORDER BY id
            """)
            for f in c.fetchall():
                (id_, titulo, estado, autor, dni, tel, mail, creado) = f
                print(f"\n   #{id_}  {titulo or '(sin título)'}")
                print(f"        estado    {estado or '—'}")
                print(f"        cargó     {autor or '—'} (DNI {dni or '—'})")
                print(f"        contacto  {tel or '—'} · {mail or '—'}")
                print(f"        fecha     {creado or '—'}")

            # Un registro sin DNI no lo puede editar nadie (ver puede_modificar).
            c.execute("SELECT COUNT(*) FROM estudios "
                      "WHERE creado_por_dni IS NULL OR creado_por_dni = ''")
            sin_dni = c.fetchone()[0]
            if sin_dni:
                print(f"\n   ATENCION: {sin_dni} investigacion(es) sin DNI de autor. "
                      "Nadie las va a poder modificar.")


if __name__ == "__main__":
    main()

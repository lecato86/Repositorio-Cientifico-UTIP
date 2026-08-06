"""Backup y restore de la base de datos de OAFCare.

Hace un dump completo de todas las tablas a un archivo JSON con timestamp
(para restaurar) y además exporta la base a CSV (una planilla por tabla,
para abrir en Excel), o restaura uno de esos JSON. Funciona contra el motor
que esté configurado en .env: Postgres si hay DATABASE_URL (producción /
Neon), SQLite si no (desarrollo local).

Uso:
    # Crear un backup. Genera:
    #   backups/oafcare_backup_AAAAMMDD_HHMMSS.json       (para restaurar)
    #   backups/oafcare_backup_AAAAMMDD_HHMMSS_csv/*.csv  (para Excel)
    python scripts/backup_db.py

    # Restaurar un backup (solo si las tablas destino están vacías)
    python scripts/backup_db.py --restore backups/oafcare_backup_20260706_150000.json

    # Restaurar PISANDO los datos existentes (borra las tablas primero)
    python scripts/backup_db.py --restore <archivo> --force

Los backups contienen datos de pacientes: NUNCA se commitean (backups/
está en .gitignore).
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime

# Permite ejecutar el script desde cualquier carpeta.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config, BASE_DIR

TABLAS = ["pacientes", "atenciones_diarias", "historial", "usuarios"]
BACKUP_DIR = os.path.join(BASE_DIR, "backups")


def _conectar():
    """Devuelve (conexion, motor). Motor: 'postgres' o 'sqlite'.

    Prioridad: BACKUP_DATABASE_URL (la base de producción, ej. Neon) ->
    DATABASE_URL -> SQLite local. Así el backup semanal alcanza a la base
    real aunque la app local trabaje con SQLite.
    """
    url = Config.BACKUP_DATABASE_URL or Config.DATABASE_URL
    if url:
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(url, row_factory=dict_row), "postgres"

    import sqlite3

    if not os.path.exists(Config.DATABASE):
        raise SystemExit(f"No existe la base SQLite: {Config.DATABASE}")
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"


# Columnas conocidas de cada tabla. Se usan para exportar a CSV con
# encabezados aunque la tabla esté vacía (así el archivo siempre es legible).
COLUMNAS = {
    "pacientes": ["hc", "nombre", "edad", "diagnostico", "soporte", "sala",
                  "ultima_actualizacion", "estado", "fecha_alta", "muestra", "tq"],
    "atenciones_diarias": ["id", "hc", "fecha", "atenciones"],
    "historial": ["id", "hc", "campo", "valor_anterior", "valor_nuevo", "fecha"],
    "usuarios": ["id", "username", "password_hash", "rol"],
}


def _exportar_csv(datos, carpeta) -> None:
    """Escribe una planilla CSV por tabla (para abrir en Excel).

    Usa utf-8-sig para que Excel muestre bien los acentos. Aunque una tabla
    esté vacía, deja el CSV con la fila de encabezados.
    """
    os.makedirs(carpeta, exist_ok=True)
    for tabla, filas in datos.items():
        columnas = list(filas[0].keys()) if filas else COLUMNAS.get(tabla, [])
        ruta = os.path.join(carpeta, f"{tabla}.csv")
        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columnas)
            writer.writeheader()
            writer.writerows(filas)


def hacer_backup() -> None:
    conn, motor = _conectar()
    try:
        datos = {}
        for tabla in TABLAS:
            filas = conn.execute(f"SELECT * FROM {tabla}").fetchall()
            datos[tabla] = [dict(f) for f in filas]

        ahora = datetime.now()
        backup = {
            "app": "oafcare",
            "motor": motor,
            "fecha": ahora.isoformat(timespec="seconds"),
            "tablas": datos,
        }
    finally:
        conn.close()

    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = ahora.strftime("%Y%m%d_%H%M%S")
    ruta = os.path.join(BACKUP_DIR, f"oafcare_backup_{stamp}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=1)

    # Además del JSON (que sirve para restaurar), exportamos la base a CSV
    # (una planilla por tabla) para poder abrirla y leerla en Excel.
    carpeta_csv = os.path.join(BACKUP_DIR, f"oafcare_backup_{stamp}_csv")
    _exportar_csv(datos, carpeta_csv)

    print(f"Backup creado: {ruta}  (motor: {motor})")
    for tabla in TABLAS:
        print(f"  {tabla}: {len(datos[tabla])} filas")
    print(f"Export CSV (para Excel) en: {carpeta_csv}")


def restaurar(ruta: str, force: bool) -> None:
    with open(ruta, encoding="utf-8") as f:
        backup = json.load(f)
    if backup.get("app") != "oafcare" or "tablas" not in backup:
        raise SystemExit(f"El archivo no parece un backup de OAFCare: {ruta}")

    conn, motor = _conectar()
    ph = "%s" if motor == "postgres" else "?"
    try:
        # Chequeo de seguridad: no pisar datos existentes salvo --force.
        with_datos = [
            t for t in TABLAS
            if conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"] > 0
        ]
        if with_datos and not force:
            raise SystemExit(
                f"Las tablas {', '.join(with_datos)} ya tienen datos. "
                "Para pisarlos ejecutá de nuevo con --force (¡borra lo actual!)."
            )

        for tabla in TABLAS:
            if force:
                conn.execute(f"DELETE FROM {tabla}")
            filas = backup["tablas"].get(tabla, [])
            for fila in filas:
                cols = list(fila.keys())
                sql = (
                    f"INSERT INTO {tabla} ({', '.join(cols)}) "
                    f"VALUES ({', '.join([ph] * len(cols))})"
                )
                conn.execute(sql, tuple(fila[c] for c in cols))
            print(f"  {tabla}: {len(filas)} filas restauradas")

        # En Postgres, alinear las secuencias SERIAL con los ids insertados.
        if motor == "postgres":
            for tabla in ("atenciones_diarias", "historial", "usuarios"):
                conn.execute(
                    f"SELECT setval(pg_get_serial_sequence('{tabla}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {tabla}), 1))"
                )

        conn.commit()
        print(f"Restore completado desde {ruta} (motor destino: {motor})")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--restore", metavar="ARCHIVO", help="Archivo JSON de backup a restaurar")
    parser.add_argument("--force", action="store_true", help="Al restaurar, borra los datos actuales primero")
    args = parser.parse_args()

    if args.restore:
        restaurar(args.restore, args.force)
    else:
        hacer_backup()


if __name__ == "__main__":
    main()

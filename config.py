import os
from dotenv import load_dotenv

# Directorio raíz del proyecto (donde está este config.py).
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Ruta explícita al .env para que se encuentre sin importar desde dónde se
# ejecute (doble clic, Programador de tareas de Windows, gunicorn, etc.).
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _resolver_db(valor: str) -> str:
    """Devuelve siempre una ruta ABSOLUTA a la base de datos SQLite.

    Si DATABASE viene relativa (o no viene), se ancla al directorio del
    proyecto. Así la app usa SIEMPRE el mismo archivo sin importar desde
    qué carpeta se la ejecute (python app.py, run_dev.py, gunicorn, systemd,
    doble clic, etc.).
    """
    if os.path.isabs(valor):
        return valor
    return os.path.join(BASE_DIR, valor)


def _normalizar_pg_url(url: str) -> str:
    """Normaliza la URL de Postgres.

    Algunos proveedores entregan 'postgres://' pero las libs modernas esperan
    'postgresql://'. También deja pasar None/'' sin tocar.
    """
    if not url:
        return url
    # Quita cualquier espacio o salto de línea que se haya colado al pegar la
    # URL (ej: el panel de Render parte los valores largos). Una URL de
    # conexión nunca contiene espacios, así que es seguro eliminarlos todos.
    url = "".join(url.split())
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def _parse_admin_dnis(raw: str):
    """Parsea ADMIN_DNIS a una lista de DNIs normalizados (solo dígitos).

    Formato esperado:  30123456,28999111
    Se aceptan puntos y espacios al escribirlos ('30.123.456'): se limpian acá
    con la MISMA regla que usa el login, así el DNI del .env matchea con el que
    la persona tipea.
    """
    dnis = []
    for item in (raw or "").split(","):
        limpio = "".join(ch for ch in item if ch.isdigit())
        if limpio and limpio not in dnis:
            dnis.append(limpio)
    return dnis


def _parse_int(valor, default):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return default


class Config:
    """Configuración central de la app, leída desde variables de entorno.

    TODA lectura de os.environ vive acá. El resto del código accede a estos
    valores con current_app.config["NOMBRE"], nunca con os.getenv() directo.
    """

    SECRET_KEY = os.environ.get("SECRET_KEY")

    # Si DATABASE_URL está seteada (ej: Postgres de Neon en Render) se usa
    # Postgres. Si no, se cae a SQLite local (archivo DATABASE) para desarrollo.
    DATABASE_URL = _normalizar_pg_url(os.environ.get("DATABASE_URL"))
    DATABASE = _resolver_db(os.environ.get("DATABASE", "pacientes.db"))

    # Usada SOLO por scripts/backup_db.py: permite backupear la base de
    # PRODUCCIÓN (Neon) desde una máquina local sin que la app local deje
    # de usar SQLite. Si está vacía, el backup cae a DATABASE_URL y, en su
    # defecto, a la SQLite local.
    BACKUP_DATABASE_URL = _normalizar_pg_url(os.environ.get("BACKUP_DATABASE_URL"))

    DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

    # Render setea RENDER=true automáticamente en todos sus servicios.
    # La usamos para exigir Postgres allá SIEMPRE: el disco de Render es
    # efímero, y una app corriendo con SQLite ahí pierde todos los datos
    # en cada deploy/reinicio (ya pasó una vez — nunca más).
    EN_RENDER = bool(os.environ.get("RENDER"))

    # DNIs con rol de administrador. El acceso a la app NO tiene contraseña:
    # se entra con nombre y apellido + DNI, y todo el que entra puede cargar y
    # editar sus propias investigaciones. Los DNIs de esta lista, además,
    # pueden borrar registros del repositorio.
    # Vacía es válido: simplemente no hay administradores.
    ADMIN_DNIS = _parse_admin_dnis(os.environ.get("ADMIN_DNIS", ""))

    # A quién escribirle para pedir que se archive o se borre una
    # investigación. Se muestra al pie de la pantalla de modificar, en chico:
    # nadie borra por su cuenta, se pide.
    # Tienen valor por defecto para que el aviso aparezca sin configurar nada
    # en el panel de Render; se pueden pisar por entorno. Vacías: no se muestra.
    CONTACTO_ADMIN_MAIL = os.environ.get(
        "CONTACTO_ADMIN_MAIL", "rossicatriel@gmail.com"
    )
    CONTACTO_ADMIN_TEL = os.environ.get("CONTACTO_ADMIN_TEL", "3512477329")

    # Servidor local (run_server.py / run_dev.py). En producción manda gunicorn.
    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = _parse_int(os.environ.get("PORT"), 5000)

    @classmethod
    def validate(cls):
        """Valida que las variables obligatorias estén presentes al arranque.

        - SECRET_KEY: siempre obligatoria (firma las sesiones).
        - DATABASE_URL: obligatoria en producción (DEBUG=False) y SIEMPRE que
          la app corra en Render, aunque alguien setee DEBUG=True allá: el
          disco de Render es efímero y SQLite ahí pierde los datos en cada
          deploy. En desarrollo local sí se permite SQLite.
        """
        faltantes = []

        if not cls.SECRET_KEY:
            faltantes.append(
                "SECRET_KEY — clave para firmar sesiones. "
                "Generá una con: python -c \"import secrets; print(secrets.token_hex(32))\""
            )

        if (not cls.DEBUG or cls.EN_RENDER) and not cls.DATABASE_URL:
            faltantes.append(
                "DATABASE_URL — conexión a Postgres (obligatoria en producción "
                "y siempre en Render: sin ella la app usaría SQLite en disco "
                "efímero y los datos se perderían en cada deploy). "
                "Formato: postgresql://usuario:password@host/basededatos?sslmode=require"
            )

        if faltantes:
            raise RuntimeError(
                "Faltan variables de entorno obligatorias:\n  - "
                + "\n  - ".join(faltantes)
                + "\n\nSolución: copiá '.env.example' a '.env' y completá los valores. "
                "En producción (Render), configuralas en el panel Environment."
            )

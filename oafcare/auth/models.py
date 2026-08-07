"""Identificación de usuarios por nombre y apellido + DNI (sin contraseña).

**No hay tabla de usuarios.** La persona escribe su nombre y su DNI y entra;
esos dos datos viajan en la cookie de sesión (firmada con SECRET_KEY) y se
reconstruyen en cada request. La única tabla de la app es `estudios`.

El DNI es la identidad: es lo que se guarda junto a cada investigación y lo que
después se compara para permitir modificarla. El nombre es solo para mostrar
(dos personas pueden llamarse igual; dos DNIs no).
"""

from flask import current_app
from flask_login import LoginManager, UserMixin

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Ingresá con tu nombre y tu DNI para continuar."

# Separa DNI de nombre dentro del id de sesión. El DNI es solo dígitos, así que
# el primer separador nunca es ambiguo.
_SEP = "|"


def normalizar_dni(dni: str) -> str:
    """Deja solo los dígitos del DNI.

    Así '30.123.456', '30 123 456' y '30123456' son el MISMO usuario: sin esto,
    alguien que un día escribe los puntos y otro día no quedaría como dos
    personas distintas y no podría editar sus propias investigaciones.
    """
    return "".join(ch for ch in (dni or "") if ch.isdigit())


def normalizar_nombre(nombre: str) -> str:
    """Colapsa los espacios de más y recorta. No cambia mayúsculas: el nombre
    se muestra tal como la persona lo escribió."""
    return " ".join((nombre or "").split())


class Usuario(UserMixin):
    """Usuario en sesión. No corresponde a ninguna fila: se arma desde la cookie."""

    def __init__(self, nombre: str, dni: str):
        self.nombre = nombre
        self.dni = dni

    def get_id(self):
        """Lo que flask_login guarda en la cookie de sesión.

        Lleva los dos datos porque no hay base de donde releer el nombre.
        """
        return f"{self.dni}{_SEP}{self.nombre}"

    @property
    def rol(self) -> str:
        """'admin' si el DNI está en ADMIN_DNIS, 'editor' para cualquier otro.

        Se calcula en cada request desde la config, no se guarda: alcanza con
        tocar ADMIN_DNIS en el entorno para dar o sacar permisos.
        """
        if self.dni in (current_app.config.get("ADMIN_DNIS") or []):
            return "admin"
        return "editor"

    @property
    def username(self):
        """Alias de `nombre`, por si alguna plantilla lo usa con ese nombre."""
        return self.nombre


@login_manager.user_loader
def cargar_usuario(user_id: str):
    """Reconstruye el Usuario desde el id guardado en la sesión.

    Los valores se vuelven a normalizar: la cookie está firmada, pero igual se
    tratan como entrada.
    """
    dni, _, nombre = (user_id or "").partition(_SEP)
    return ingresar(nombre, dni)


def ingresar(nombre: str, dni: str):
    """Devuelve el Usuario para el par (nombre, DNI), o None si falta alguno.

    No hay registro ni verificación de identidad: es un repositorio interno de
    la UTIP y el DNI sirve para saber quién cargó cada investigación.
    """
    nombre = normalizar_nombre(nombre)
    dni = normalizar_dni(dni)
    if not nombre or not dni:
        return None
    return Usuario(nombre=nombre, dni=dni)

from functools import wraps
from flask_login import current_user


def requiere_editor(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.rol not in ("admin", "editor"):
            return "<h3>No tienes permisos para realizar esta acción.</h3>"
        return f(*args, **kwargs)
    return decorated


def requiere_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.rol != "admin":
            return "<h3>Solo un administrador puede realizar esta acción.</h3>", 403
        return f(*args, **kwargs)
    return decorated

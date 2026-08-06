from flask_login import LoginManager, UserMixin
from werkzeug.security import check_password_hash

login_manager = LoginManager()
login_manager.login_view = "auth.login"


class Usuario(UserMixin):
    def __init__(self, id: str, username: str, rol: str):
        self.id = id
        self.username = username
        self.rol = rol


@login_manager.user_loader
def cargar_usuario(user_id: str):
    from oafcare.database import get_db
    row = get_db().execute(
        "SELECT id, username, rol FROM usuarios WHERE id = ?", (user_id,)
    ).fetchone()
    if row:
        return Usuario(id=str(row["id"]), username=row["username"], rol=row["rol"])
    return None


def authenticate(username: str, password: str):
    from oafcare.database import get_db
    row = get_db().execute(
        "SELECT id, username, password_hash, rol FROM usuarios WHERE username = ?",
        (username,),
    ).fetchone()
    if row and check_password_hash(row["password_hash"], password):
        return Usuario(id=str(row["id"]), username=row["username"], rol=row["rol"])
    return None

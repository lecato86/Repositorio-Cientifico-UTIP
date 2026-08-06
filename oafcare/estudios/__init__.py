from flask import Blueprint

estudios_bp = Blueprint("estudios", __name__)

from . import routes  # noqa: E402,F401  (registra las rutas en el blueprint)

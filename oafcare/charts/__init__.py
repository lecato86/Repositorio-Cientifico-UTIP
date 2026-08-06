from flask import Blueprint

charts_bp = Blueprint("charts", __name__)

from . import routes  # noqa

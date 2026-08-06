from flask import Blueprint

patients_bp = Blueprint("patients", __name__)

from . import routes  # noqa

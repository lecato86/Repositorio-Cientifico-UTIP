from flask import Flask
from config import Config
from .database import close_db, init_db
from .auth.models import login_manager
from .utils.soporte import SALAS, SOPORTES
from .utils.muestras import MUESTRAS
from .utils.edad import formato_edad
from .utils.ingreso import (
    SEXOS, SALAS_DERIVACION, ESTADOS_VIRUS, VIRUS_PANEL, COMORBILIDADES,
    SOPORTES_PREVIOS, LUGARES_INICIO, COMPLICACIONES, RESULTADOS_OAF,
    TIEMPOS_MEDICION, PARAMETROS_MEDICION,
)


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(config_class)
    config_class.validate()

    login_manager.init_app(app)
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()

    from .auth import auth_bp
    app.register_blueprint(auth_bp)

    from .patients import patients_bp
    app.register_blueprint(patients_bp)

    from .charts import charts_bp
    app.register_blueprint(charts_bp)

    @app.context_processor
    def inject_globals():
        return {
            "SALAS": SALAS,
            "SOPORTES": SOPORTES,
            "MUESTRAS": MUESTRAS,
            "SEXOS": SEXOS,
            "SALAS_DERIVACION": SALAS_DERIVACION,
            "ESTADOS_VIRUS": ESTADOS_VIRUS,
            "VIRUS_PANEL": VIRUS_PANEL,
            "COMORBILIDADES": COMORBILIDADES,
            "SOPORTES_PREVIOS": SOPORTES_PREVIOS,
            "LUGARES_INICIO": LUGARES_INICIO,
            "COMPLICACIONES": COMPLICACIONES,
            "RESULTADOS_OAF": RESULTADOS_OAF,
            "TIEMPOS_MEDICION": TIEMPOS_MEDICION,
            "PARAMETROS_MEDICION": PARAMETROS_MEDICION,
        }

    app.jinja_env.filters["formato_edad"] = formato_edad

    return app

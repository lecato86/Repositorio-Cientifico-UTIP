from flask import Flask
from config import Config
from .database import close_db, init_db
from .auth.models import login_manager
from .utils.estudio import (
    FUENTES_DATOS, FUENTE_DATOS_OTRA, TEMPORALIDADES,
    OTRAS_INSTITUCIONES, OTRAS_INSTITUCIONES_SI, ESTADOS_INVESTIGACION,
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

    # Repositorio científico (investigaciones): el único dominio de la app.
    from .estudios import estudios_bp
    app.register_blueprint(estudios_bp)

    @app.context_processor
    def inject_globals():
        """Opciones fijas del formulario, disponibles en todas las plantillas."""
        return {
            # Apartado 1: sobre el estudio
            "FUENTES_DATOS": FUENTES_DATOS,
            "FUENTE_DATOS_OTRA": FUENTE_DATOS_OTRA,
            "TEMPORALIDADES": TEMPORALIDADES,
            # Apartado 2: investigadores
            "OTRAS_INSTITUCIONES": OTRAS_INSTITUCIONES,
            "OTRAS_INSTITUCIONES_SI": OTRAS_INSTITUCIONES_SI,
            "ESTADOS_INVESTIGACION": ESTADOS_INVESTIGACION,
        }

    return app

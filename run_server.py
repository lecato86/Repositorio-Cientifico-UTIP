"""Arranca OAFCare accesible desde la red (no solo localhost).

Uso:
    python run_server.py

Escucha en http://0.0.0.0:5000 -> accesible desde otras PCs de la red/VPN
usando la IP del servidor, por ej. http://192.168.1.106:5000
"""
from oafcare import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=app.config["DEBUG"],
        use_reloader=False,
    )

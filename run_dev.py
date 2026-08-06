from livereload import Server
from oafcare import create_app

app = create_app()
server = Server(app.wsgi_app)
server.watch("templates/")
server.watch("static/")
server.watch("oafcare/")
server.serve(host=app.config["HOST"], port=app.config["PORT"])

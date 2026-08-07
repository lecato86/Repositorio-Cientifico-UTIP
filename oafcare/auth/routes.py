from flask import request, redirect, url_for, render_template
from flask_login import login_user, logout_user, login_required
from . import auth_bp
from .models import ingresar


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Ingreso sin contraseña: nombre y apellido + DNI.

    No hay verificación de identidad — es un repositorio interno de la UTIP y
    el DNI sirve para saber quién cargó cada investigación, no para autenticar.
    """
    error = ""
    nombre = ""
    dni = ""

    if request.method == "POST":
        nombre = request.form.get("nombre", "")
        dni = request.form.get("dni", "")
        usuario = ingresar(nombre, dni)
        if usuario:
            login_user(usuario)
            return redirect(url_for("estudios.inicio"))
        error = "Completá tu nombre y apellido y un DNI con números."

    return render_template("auth/login.html", error=error, nombre=nombre, dni=dni)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))

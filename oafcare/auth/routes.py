from flask import request, redirect, url_for, render_template
from flask_login import login_user, logout_user, login_required
from . import auth_bp
from .models import authenticate


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        usuario = authenticate(username, password)
        if usuario:
            login_user(usuario)
            return redirect(url_for("patients.home"))
        error = "Usuario o contraseña incorrectos."
    return render_template("auth/login.html", error=error)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))

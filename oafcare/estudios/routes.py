"""Rutas del repositorio científico: inicio, carga, consulta y modificación."""

from flask import render_template, request, redirect, url_for
from flask_login import login_required, current_user

from . import estudios_bp
from .models import (
    crear_estudio, actualizar_estudio, get_estudio, get_todos_estudios,
    buscar_estudios_por_titulo, borrar_estudio,
)
from oafcare.auth.decorators import requiere_editor, requiere_admin
from oafcare.utils.estudio import estudio_desde_form
from oafcare.utils.repositorio import (
    GRUPOS_REPOSITORIO, COLUMNAS_REPOSITORIO, COLUMNAS_FIJAS, COLUMNAS_LARGAS,
    resumen_repositorio,
)
from oafcare.utils.docs import documentos_disponibles


# ------------------ INICIO (menú principal) ------------------

@estudios_bp.route("/")
@login_required
def inicio():
    """Pantalla de inicio: menú con las cuatro acciones del repositorio."""
    return render_template("estudios/inicio.html")


# ------------------ CARGAR NUEVA INVESTIGACIÓN ------------------

@estudios_bp.route("/nueva-investigacion")
@login_required
@requiere_editor
def nueva():
    """Formulario de carga, vacío."""
    return render_template(
        "estudios/nueva.html",
        e={},
        form_action=url_for("estudios.guardar"),
        titulo_pagina="Cargar nueva investigación",
        submit_label="Guardar investigación",
    )


@estudios_bp.route("/nueva-investigacion", methods=["POST"])
@login_required
@requiere_editor
def guardar():
    datos = estudio_desde_form(request.form)
    if not datos["titulo"]:
        return "El título del estudio es obligatorio.", 400

    crear_estudio(datos, current_user.username)

    return redirect(url_for("estudios.repositorio"))


# ------------------ CONSULTAR REPOSITORIO ------------------

@estudios_bp.route("/repositorio")
@login_required
def repositorio():
    """Visualización completa de la base de investigaciones.

    Las columnas y su agrupación se declaran en `utils/repositorio.py`.
    """
    estudios = get_todos_estudios()

    return render_template(
        "estudios/repositorio.html",
        estudios=estudios,
        grupos=GRUPOS_REPOSITORIO,
        columnas=COLUMNAS_REPOSITORIO,
        columnas_fijas=COLUMNAS_FIJAS,
        columnas_largas=COLUMNAS_LARGAS,
        resumen=resumen_repositorio(estudios),
    )


# ------------------ MODIFICAR INVESTIGACIÓN CARGADA ------------------

@estudios_bp.route("/modificar")
@login_required
@requiere_editor
def modificar():
    """Busca una investigación por TÍTULO y abre el formulario con sus datos.

    Con una sola coincidencia va derecho al formulario prellenado; con varias
    muestra la lista para elegir cuál.
    """
    titulo = request.args.get("titulo", "").strip()
    resultados = buscar_estudios_por_titulo(titulo) if titulo else []

    if len(resultados) == 1:
        return redirect(
            url_for("estudios.editar", estudio_id=resultados[0]["id"])
        )

    return render_template(
        "estudios/modificar.html", titulo=titulo, resultados=resultados
    )


@estudios_bp.route("/estudios/<int:estudio_id>/editar")
@login_required
@requiere_editor
def editar(estudio_id):
    """Formulario prellenado con todo lo guardado de una investigación."""
    estudio = get_estudio(estudio_id)
    if not estudio:
        return redirect(url_for("estudios.modificar"))

    # A dict para poder usar e.get(...) en el template (sqlite3.Row no tiene get).
    e = {k: estudio[k] for k in estudio.keys()}

    return render_template(
        "estudios/nueva.html",
        e=e,
        form_action=url_for("estudios.actualizar", estudio_id=estudio_id),
        titulo_pagina="Modificar investigación",
        submit_label="Guardar cambios",
    )


@estudios_bp.route("/estudios/<int:estudio_id>/actualizar", methods=["POST"])
@login_required
@requiere_editor
def actualizar(estudio_id):
    if not get_estudio(estudio_id):
        return redirect(url_for("estudios.modificar"))

    datos = estudio_desde_form(request.form)
    if not datos["titulo"]:
        return "El título del estudio es obligatorio.", 400

    actualizar_estudio(estudio_id, datos)

    return redirect(url_for("estudios.repositorio"))


# ------------------ BORRAR (solo admin) ------------------

@estudios_bp.route("/estudios/<int:estudio_id>/borrar", methods=["POST"])
@login_required
@requiere_admin
def borrar(estudio_id):
    borrar_estudio(estudio_id)
    return redirect(url_for("estudios.repositorio"))


# ------------------ CÓMO COMENZAR ------------------

@estudios_bp.route("/como-comenzar")
@login_required
def como_comenzar():
    """Guía de arranque + PDFs descargables (se listan desde `static/docs/`)."""
    return render_template(
        "estudios/como_comenzar.html", documentos=documentos_disponibles()
    )

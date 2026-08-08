"""Rutas del repositorio científico: inicio, carga, consulta y modificación."""

from flask import render_template, request, redirect, url_for
from flask_login import login_required, current_user

from . import estudios_bp
from .models import (
    crear_estudio, actualizar_estudio, get_estudio, get_todos_estudios,
    buscar_estudios_por_titulo, borrar_estudio, puede_modificar,
)
from oafcare.auth.decorators import requiere_editor, requiere_admin
from oafcare.utils.estudio import estudio_desde_form, faltantes
from oafcare.utils.repositorio import (
    GRUPOS_REPOSITORIO, COLUMNAS_REPOSITORIO, COLUMNAS_FIJAS, COLUMNAS_LARGAS,
    resumen_repositorio, etapa_de,
)
from oafcare.utils.docs import documentos_disponibles


# Mensaje único para cuando alguien intenta editar una investigación ajena.
# Consultarla puede cualquiera; modificarla, solo quien la cargó.
MSG_NO_ES_TU_ESTUDIO = "SOLO EL USUARIO QUE CARGÓ ESTE TRABAJO PUEDE MODIFICARLO"


def _bloqueo_ajeno(estudio):
    """Pantalla de "no es tuyo" para una investigación de otra persona."""
    return render_template(
        "estudios/no_autorizado.html",
        estudio=estudio,
        mensaje=MSG_NO_ES_TU_ESTUDIO,
    ), 403


def _falta_algo(datos):
    """Mensaje 400 si falta un campo obligatorio, o None si está todo.

    El formulario ya los marca `required`, pero el POST es una URL más y puede
    llegar sin pasar por él (o con el JS desactivado).
    """
    falta = faltantes(datos)
    if not falta:
        return None

    if len(falta) == 1:
        detalle = falta[0]
    else:
        detalle = ", ".join(falta[:-1]) + " y " + falta[-1]

    return f"Falta completar {detalle}.", 400


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
    error = _falta_algo(datos)
    if error:
        return error

    crear_estudio(datos, current_user.nombre, current_user.dni)

    return redirect(url_for("estudios.repositorio"))


# ------------------ CONSULTAR REPOSITORIO ------------------

@estudios_bp.route("/repositorio")
@login_required
def repositorio():
    """Las investigaciones cargadas, en tarjetas (por defecto) o en tabla.

    `?vista=tabla` muestra la planilla completa, con todas las columnas. Sin
    ese parámetro se ven las tarjetas: la tabla tiene 15 columnas y para
    leerla hay que scrollear en horizontal, así que sirve para comparar pero
    no para mirar el repositorio.

    Las columnas y su agrupación se declaran en `utils/repositorio.py`.
    """
    estudios = get_todos_estudios()
    vista = "tabla" if request.args.get("vista") == "tabla" else "tarjetas"

    # El botón "Modificar" solo aparece en las propias: el resto se consultan
    # pero no se editan.
    editables = {e["id"]: puede_modificar(e, current_user) for e in estudios}
    etapas = {e["id"]: etapa_de(e["estado_actual"]) for e in estudios}

    return render_template(
        "estudios/repositorio.html",
        estudios=estudios,
        vista=vista,
        grupos=GRUPOS_REPOSITORIO,
        columnas=COLUMNAS_REPOSITORIO,
        columnas_fijas=COLUMNAS_FIJAS,
        columnas_largas=COLUMNAS_LARGAS,
        resumen=resumen_repositorio(estudios),
        editables=editables,
        etapas=etapas,
    )


@estudios_bp.route("/estudios/<int:estudio_id>")
@login_required
def detalle(estudio_id):
    """Ficha de una investigación: todos sus datos, agrupados por apartado.

    Es la pantalla a la que se entra desde una tarjeta del repositorio. La
    puede ver cualquiera; el botón de modificar solo aparece para su autor.
    """
    estudio = get_estudio(estudio_id)
    if not estudio:
        return redirect(url_for("estudios.repositorio"))

    return render_template(
        "estudios/detalle.html",
        e=estudio,
        grupos=GRUPOS_REPOSITORIO,
        etapa=etapa_de(estudio["estado_actual"]),
        puede_editar=puede_modificar(estudio, current_user),
    )


# ------------------ MODIFICAR INVESTIGACIÓN CARGADA ------------------

@estudios_bp.route("/modificar")
@login_required
@requiere_editor
def modificar():
    """Busca una investigación por TÍTULO y abre el formulario con sus datos.

    La búsqueda muestra TODAS las coincidencias, sean de quien sean: consultar
    puede cualquiera. Lo que se marca en la lista es cuáles puede modificar
    quien está usando la app (las que cargó con su mismo DNI).

    Con una sola coincidencia propia va derecho al formulario prellenado; si es
    ajena o hay varias, se muestra la lista.
    """
    titulo = request.args.get("titulo", "").strip()
    resultados = buscar_estudios_por_titulo(titulo) if titulo else []

    # El template necesita saber, por cada resultado, si es editable.
    editables = {
        r["id"]: puede_modificar(r, current_user) for r in resultados
    }

    if len(resultados) == 1 and editables[resultados[0]["id"]]:
        return redirect(
            url_for("estudios.editar", estudio_id=resultados[0]["id"])
        )

    return render_template(
        "estudios/modificar.html",
        titulo=titulo,
        resultados=resultados,
        editables=editables,
        mensaje_ajeno=MSG_NO_ES_TU_ESTUDIO,
    )


@estudios_bp.route("/estudios/<int:estudio_id>/editar")
@login_required
@requiere_editor
def editar(estudio_id):
    """Formulario prellenado con todo lo guardado de una investigación.

    Solo lo abre quien la cargó: se compara el DNI del autor con el del usuario
    en sesión.
    """
    estudio = get_estudio(estudio_id)
    if not estudio:
        return redirect(url_for("estudios.modificar"))

    if not puede_modificar(estudio, current_user):
        return _bloqueo_ajeno(estudio)

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
    estudio = get_estudio(estudio_id)
    if not estudio:
        return redirect(url_for("estudios.modificar"))

    # Se vuelve a chequear acá y no solo en `editar`: el POST es una URL más y
    # podría llegar sin haber pasado por el formulario.
    if not puede_modificar(estudio, current_user):
        return _bloqueo_ajeno(estudio)

    datos = estudio_desde_form(request.form)
    error = _falta_algo(datos)
    if error:
        return error

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

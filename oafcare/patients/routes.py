from flask import request, redirect, url_for, send_file, Response, current_app, render_template
from flask_login import login_required, current_user
from datetime import datetime
import io
import csv
import os
from . import patients_bp
from .models import (
    get_paciente, get_pacientes_activos, get_pacientes_alta,
    get_ultima_entrada, insert_atencion, update_atencion,
    upsert_paciente, log_historial, get_historial_paciente,
    get_atenciones_paciente, dar_alta, get_inactivos,
    buscar_pacientes, get_historial_exportar, get_deduplicacion_pendiente,
    borrar_paciente, guardar_mediciones_oaf, get_mediciones_oaf,
)
from .services import trayectoria_ventilatoria_data
from oafcare.auth.decorators import requiere_editor, requiere_admin
from oafcare.utils.edad import (
    edad_meses_desde_form, edad_partes, formato_edad,
)
from oafcare.utils.soporte import soporte_desde_form
from oafcare.utils.muestras import muestras_desde_form, muestras_seleccionadas
from oafcare.utils.ingreso import (
    sexo_desde_form, peso_desde_form, sala_derivacion_desde_form,
    virus_desde_form, comorbilidades_desde_form,
    soporte_previo_desde_form, lugar_inicio_desde_form,
    complicaciones_desde_form, resultado_desde_form, mediciones_desde_form,
    virus_seleccionados, comorbilidades_seleccionadas,
    complicaciones_seleccionadas, mediciones_valores,
)


# ------------------ HELPERS DE INGRESO ------------------

def _ingreso_desde_form(data):
    """Lee del form todos los campos de ingreso -> dict con claves = columnas
    de PACIENTE_COLUMNAS_INGRESO. Usado por 'guardar' y 'actualizar_ultima'."""
    return {
        "sexo": sexo_desde_form(data),
        "peso": peso_desde_form(data),
        "fecha_inicio_oaf": data.get("fecha_inicio_oaf", "").strip(),
        "hora_inicio_oaf": data.get("hora_inicio_oaf", "").strip(),
        "sala_derivacion": sala_derivacion_desde_form(data),
        "soporte_previo_oaf": soporte_previo_desde_form(data),
        "lugar_inicio_oaf": lugar_inicio_desde_form(data),
        "fecha_inicio_alimentacion": data.get("fecha_inicio_alimentacion", "").strip(),
        "comorbilidades": comorbilidades_desde_form(data),
        "complicaciones": complicaciones_desde_form(data),
        "fecha_fin_oaf": data.get("fecha_fin_oaf", "").strip(),
        "hora_fin_oaf": data.get("hora_fin_oaf", "").strip(),
        "resultado_oaf": resultado_desde_form(data),
        **virus_desde_form(data),
    }


def _log_cambios(hc, paciente, nuevos, fecha):
    """Loguea en historial cada campo cuyo valor cambió respecto del paciente
    existente. `nuevos` es {campo: valor_nuevo}. No loguea si el paciente es
    nuevo (no hay 'valor anterior')."""
    if paciente is None:
        return
    for campo, nuevo in nuevos.items():
        viejo = paciente[campo]
        viejo = "" if viejo is None else str(viejo)
        nuevo = "" if nuevo is None else str(nuevo)
        if viejo != nuevo:
            log_historial(hc, campo, viejo, nuevo, fecha)


def _legacy_preservados(paciente):
    """Devuelve los campos legacy (soporte/sala/muestra/tq) que el formulario
    de ingreso ya no maneja, tomando el valor actual del paciente para no
    pisarlos. Para un paciente nuevo, vacíos."""
    if paciente is None:
        return {"soporte": "", "sala": "", "muestra": "", "tq": 0}
    return {
        "soporte": paciente["soporte"] or "",
        "sala": paciente["sala"] or "",
        "muestra": paciente["muestra"] or "",
        "tq": paciente["tq"] or 0,
    }


# ------------------ HOME ------------------

@patients_bp.route("/")
@login_required
def home():
    return render_template("patients/home.html", edad_anios=0, edad_meses=0)


# ------------------ GUARDAR ------------------

@patients_bp.route("/guardar", methods=["POST"])
@login_required
@requiere_editor
def guardar():
    data = request.form
    hc = data.get("hc", "").strip()
    if not hc:
        return "HC es obligatorio.", 400

    # El formulario de ingreso no trae fecha_carga: usamos la fecha de inicio
    # de OAF como fecha de la atención, y hoy como último recurso.
    fecha_carga = (
        data.get("fecha_carga", "").strip()
        or data.get("fecha_inicio_oaf", "").strip()
        or datetime.now().strftime("%Y-%m-%d")
    )
    edad_meses = edad_meses_desde_form(data)
    ingreso = _ingreso_desde_form(data)
    nombre = data.get("nombre", "")
    diagnostico = data.get("diagnostico", "")
    fecha_historial = fecha_carga + datetime.now().strftime(" %H:%M")

    # El formulario de ingreso no tiene campo de cantidad de atenciones:
    # se registra 1 por defecto (provisional; el conteo diario llega después).
    insert_atencion(hc, fecha_carga, data.get("atenciones", 1))

    # MISMA HC = actualizar el paciente existente (no duplicar) y loguear los
    # cambios en historial. Los campos legacy que el form ya no maneja se
    # conservan tomando el valor actual del paciente.
    paciente = get_paciente(hc)
    legacy = _legacy_preservados(paciente)
    estado_actual = paciente["estado"] if paciente else None

    if estado_actual == "ALTA":
        log_historial(hc, "estado", "ALTA", "REINGRESO → ACTIVO", fecha_historial)
        from oafcare.database import get_db
        db = get_db()
        db.execute(
            "UPDATE pacientes SET estado = 'ACTIVO', fecha_alta = '' WHERE hc = ?",
            (hc,),
        )
        db.commit()

    estado = "ACTIVO" if estado_actual in (None, "ALTA") else estado_actual

    nuevos = {"nombre": nombre, "edad": str(edad_meses),
              "diagnostico": diagnostico, **ingreso}
    _log_cambios(hc, paciente, nuevos, fecha_historial)

    upsert_paciente(
        hc=hc,
        nombre=nombre,
        edad=edad_meses,
        diagnostico=diagnostico,
        soporte=legacy["soporte"],
        sala=legacy["sala"],
        muestra=legacy["muestra"],
        tq=legacy["tq"],
        estado=estado,
        ultima_actualizacion=fecha_historial,
        ingreso=ingreso,
    )

    # Tabla de monitoreo (mediciones por tiempo) -> tabla mediciones_oaf.
    guardar_mediciones_oaf(hc, mediciones_desde_form(data))

    return "<a href='/'>⬅ Volver</a> | <a href='/pacientes'>📋 Pacientes</a>"


# ------------------ PACIENTES ------------------

@patients_bp.route("/pacientes")
@login_required
def listar_pacientes():
    hoy = datetime.now().strftime("%Y-%m-%d")
    datos = get_pacientes_activos(hoy)

    return render_template("patients/list.html", pacientes=datos, hoy=hoy)


# ------------------ PACIENTES ALTA ------------------

@patients_bp.route("/pacientes_alta")
@login_required
def pacientes_alta():
    pacientes = get_pacientes_alta()
    return render_template("patients/list_alta.html", pacientes=pacientes)


# ------------------ EDITAR ULTIMA ENTRADA ------------------

@patients_bp.route("/editar_ultima/<hc>")
@login_required
@requiere_editor
def editar_ultima(hc):
    paciente = get_paciente(hc)
    ultima = get_ultima_entrada(hc)
    if not paciente or not ultima:
        return redirect(url_for("patients.listar_pacientes"))

    anios, meses = edad_partes(paciente["edad"])
    p = {k: paciente[k] for k in paciente.keys()}

    return render_template(
        "patients/edit.html",
        p=p,
        edad_anios=anios,
        edad_meses=meses,
        virus_vals=virus_seleccionados(paciente),
        comorb_sel=comorbilidades_seleccionadas(paciente["comorbilidades"]),
        complic_sel=complicaciones_seleccionadas(paciente["complicaciones"]),
        med_vals=mediciones_valores(get_mediciones_oaf(hc)),
        titulo="Editar ingreso — " + hc,
        submit_label="Guardar cambios",
        hc_readonly=True,
        form_action=url_for("patients.actualizar_ultima", atencion_id=ultima["id"]),
    )


# ------------------ ACTUALIZAR ULTIMA ------------------

@patients_bp.route("/actualizar_ultima/<int:atencion_id>", methods=["POST"])
@login_required
@requiere_editor
def actualizar_ultima(atencion_id):
    data = request.form
    hc = data.get("hc", "").strip()

    paciente = get_paciente(hc)
    if not paciente:
        return redirect(url_for("patients.listar_pacientes"))

    from oafcare.database import get_db
    db = get_db()
    ultima = db.execute(
        "SELECT id, fecha, atenciones FROM atenciones_diarias "
        "WHERE hc = ? ORDER BY fecha DESC, id DESC LIMIT 1",
        (hc,),
    ).fetchone()
    if not ultima or ultima["id"] != atencion_id:
        return "Solo se puede editar la última entrada desde esta vista.", 400

    edad_meses = edad_meses_desde_form(data)
    ingreso = _ingreso_desde_form(data)
    nombre = data.get("nombre", "")
    diagnostico = data.get("diagnostico", "")
    legacy = _legacy_preservados(paciente)

    # La fecha de la atención sigue a la de inicio de OAF; si no vino, se
    # conserva la que tenía. La cantidad de atenciones no la maneja este form.
    fecha_carga = ingreso["fecha_inicio_oaf"] or ultima["fecha"] or datetime.now().strftime("%Y-%m-%d")
    fecha_historial = fecha_carga + datetime.now().strftime(" %H:%M")
    update_atencion(atencion_id, fecha_carga, ultima["atenciones"])

    nuevos = {"nombre": nombre, "edad": str(edad_meses),
              "diagnostico": diagnostico, **ingreso}
    _log_cambios(hc, paciente, nuevos, fecha_historial)

    upsert_paciente(
        hc=hc,
        nombre=nombre,
        edad=edad_meses,
        diagnostico=diagnostico,
        soporte=legacy["soporte"],
        sala=legacy["sala"],
        muestra=legacy["muestra"],
        tq=legacy["tq"],
        estado=paciente["estado"],
        ultima_actualizacion=fecha_historial,
        ingreso=ingreso,
    )

    guardar_mediciones_oaf(hc, mediciones_desde_form(data))

    return redirect(url_for("patients.listar_pacientes"))


# ------------------ DAR DE ALTA ------------------

@patients_bp.route("/dar_alta/<hc>", methods=["POST"])
@login_required
@requiere_editor
def alta(hc):
    fecha_alta = request.form.get("fecha_alta", "")
    if not fecha_alta:
        fecha_alta = datetime.now().strftime("%Y-%m-%d")

    dar_alta(hc, fecha_alta)
    log_historial(hc, "estado", "ACTIVO", "ALTA", fecha_alta + " 00:00")

    return redirect(url_for("patients.inactividad"))


# ------------------ BORRAR PACIENTE (solo admin) ------------------

@patients_bp.route("/borrar_paciente/<hc>", methods=["POST"])
@login_required
@requiere_admin
def borrar(hc):
    paciente = get_paciente(hc)
    if not paciente:
        return redirect(url_for("patients.listar_pacientes"))

    borrar_paciente(hc)

    return redirect(url_for("patients.listar_pacientes"))


# ------------------ INACTIVIDAD ------------------

@patients_bp.route("/inactividad")
@login_required
def inactividad():
    datos = get_inactivos(dias=3)

    return render_template("patients/inactive.html", pacientes=datos)


# ------------------ BUSCAR ------------------

@patients_bp.route("/buscar")
@login_required
def buscar():
    q = request.args.get("q", "").strip()
    resultados = []

    if q:
        resultados = buscar_pacientes(q)

    return render_template(
        "patients/search.html",
        query=q,
        resultados=resultados,
        deduplicacion_pendiente=get_deduplicacion_pendiente(),
    )


# ------------------ EXPORTAR PACIENTE ------------------

@patients_bp.route("/exportar_paciente/<hc>")
@login_required
def exportar_paciente(hc):
    from oafcare.database import get_db
    db = get_db()

    atenciones = db.execute("""
        SELECT a.fecha, a.hc, p.nombre, p.edad, p.diagnostico,
               p.soporte, p.tq, p.sala, p.muestra, a.atenciones
        FROM atenciones_diarias a
        LEFT JOIN pacientes p ON a.hc = p.hc
        WHERE a.hc = ?
        ORDER BY a.fecha ASC
    """, (hc,)).fetchall()

    historial = db.execute("""
        SELECT fecha, campo, valor_anterior, valor_nuevo
        FROM historial
        WHERE hc = ?
        ORDER BY fecha ASC
    """, (hc,)).fetchall()

    atenciones_rows = [
        (a["fecha"], a["hc"], a["nombre"], formato_edad(a["edad"]),
         a["diagnostico"], a["soporte"], "SI" if a["tq"] else "NO",
         a["sala"], a["muestra"], a["atenciones"])
        for a in atenciones
    ]

    archivo = os.path.join(current_app.root_path, "..", f"paciente_{hc}.csv")
    with open(archivo, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)

        writer.writerow(["=== ATENCIONES DIARIAS ==="])
        writer.writerow(["Fecha", "HC", "Nombre", "Edad",
                         "Diagnóstico", "Soporte", "TQ", "Sala", "Muestra", "Atenciones"])
        writer.writerows(atenciones_rows)

        writer.writerow([])
        writer.writerow(["=== HISTORIAL DE CAMBIOS ==="])
        writer.writerow(["Fecha", "Campo", "Valor anterior", "Valor nuevo"])
        writer.writerows([
            (h["fecha"], h["campo"], h["valor_anterior"], h["valor_nuevo"])
            for h in historial
        ])

    return send_file(archivo, as_attachment=True)

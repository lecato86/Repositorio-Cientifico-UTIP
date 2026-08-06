import time
import csv
import io
import os
from datetime import datetime

from flask import request, redirect, url_for, Response, send_file, jsonify, current_app, render_template
from flask_login import login_required

from . import charts_bp
from .matplotlib_charts import (
    generar_g1, generar_g2, generar_g3, generar_g4, generar_g5,
    generar_evo_sala, generar_evo_sop,
)
from oafcare.database import get_db
from oafcare.patients.services import trayectoria_ventilatoria_data
from oafcare.patients.models import (
    get_historial_exportar,
    get_export_agrupado,
    get_historial_paciente,
    get_paciente,
    get_atenciones_paciente,
    get_total_atenciones,
    get_mediciones_oaf,
)
from oafcare.utils.edad import formato_edad
from oafcare.utils.ingreso import (
    VIRUS_PANEL, TIEMPOS_MEDICION, PARAMETROS_MEDICION,
    SALAS_DERIVACION, LUGARES_INICIO,
)


# ------------------ CHART IMAGE ROUTES ------------------

@charts_bp.route("/g1")
@login_required
def g1():
    desde = request.args.get("desde")
    hasta = request.args.get("hasta")
    return Response(generar_g1(desde, hasta), mimetype="image/png")


@charts_bp.route("/g2")
@login_required
def g2():
    desde = request.args.get("desde")
    hasta = request.args.get("hasta")
    return Response(generar_g2(desde, hasta), mimetype="image/png")


@charts_bp.route("/g3")
@login_required
def g3():
    return Response(generar_g3(), mimetype="image/png")


@charts_bp.route("/g4")
@login_required
def g4():
    return Response(generar_g4(), mimetype="image/png")


@charts_bp.route("/g5")
@login_required
def g5():
    return Response(generar_g5(), mimetype="image/png")


@charts_bp.route("/evo_sala/<hc>")
@login_required
def evo_sala(hc):
    return Response(generar_evo_sala(hc), mimetype="image/png")


@charts_bp.route("/evo_sop/<hc>")
@login_required
def evo_sop(hc):
    return Response(generar_evo_sop(hc), mimetype="image/png")


# ------------------ API ------------------

@charts_bp.route("/api/trayectoria_ventilatoria/<hc>")
@login_required
def api_trayectoria(hc):
    return jsonify(trayectoria_ventilatoria_data(hc))


# ------------------ ESTADISTICAS ------------------

@charts_bp.route("/estadisticas")
@login_required
def estadisticas():
    db = get_db()
    c = db.cursor()

    c.execute('''
    SELECT
        fecha,
        COUNT(DISTINCT hc) as total_pacientes,
        SUM(atenciones) as total_atenciones
    FROM atenciones_diarias
    GROUP BY fecha
    ORDER BY fecha DESC
    ''')

    datos = c.fetchall()

    return render_template("charts/statistics.html", datos=datos)


# ------------------ TRAYECTORIA VENTILATORIA ------------------

@charts_bp.route("/trayectoria_ventilatoria/<hc>")
@login_required
def trayectoria_ventilatoria(hc):
    datos = trayectoria_ventilatoria_data(hc)
    return render_template("patients/trajectory.html", hc=hc, trayectoria_data=datos)


# ------------------ EVOLUCION ------------------

@charts_bp.route("/evolucion/<hc>")
@login_required
def evolucion(hc):
    db = get_db()
    c = db.cursor()

    # Historial COMPLETO: todos los campos que se fueron modificando,
    # no solo soporte/sala. Así se ve la evolución completa del paciente.
    c.execute("""
        SELECT campo, valor_anterior, valor_nuevo, fecha
        FROM historial
        WHERE hc = ?
        ORDER BY fecha ASC
    """, (hc,))

    rows = c.fetchall()
    historial = [
        {"campo": r[0], "valor_anterior": r[1], "valor_nuevo": r[2], "fecha": r[3]}
        for r in rows
    ]

    paciente = get_paciente(hc)
    trayectoria_data = trayectoria_ventilatoria_data(hc)
    total_atenciones = get_total_atenciones(hc)

    return render_template(
        "patients/evolution.html",
        hc=hc,
        paciente=paciente,
        historial=historial,
        trayectoria_data=trayectoria_data,
        total_atenciones=total_atenciones,
    )


# ------------------ EXPORTAR CSV ------------------

def _hc_key(p):
    """Orden ascendente por número de HC (numérico si se puede, si no texto)."""
    hc = (p["hc"] or "").strip()
    try:
        return (0, int(hc), "")
    except (ValueError, TypeError):
        return (1, 0, hc)


def _cs(v):
    """Sanitiza una celda para Excel: evita que interprete '=', '+', '-' o '@'
    iniciales como fórmula (les antepone comilla simple)."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


def _fecha_hora(fecha, hora):
    return " ".join(x for x in [(fecha or "").strip(), (hora or "").strip()] if x)


@charts_bp.route("/exportar")
@login_required
def exportar():
    db = get_db()
    pacientes = sorted(
        db.execute("SELECT * FROM pacientes").fetchall(),
        key=_hc_key,
    )

    # Mediciones de monitoreo por paciente, indexadas por 'orden'. Se usan para
    # el cuadro de monitoreo Y para el Score de TAL en Hora 0 del resumen.
    med_por_paciente = {}
    for p in pacientes:
        idx = {}
        for m in get_mediciones_oaf(p["hc"]):
            try:
                idx[int(m["orden"])] = m
            except (TypeError, ValueError):
                pass
        med_por_paciente[p["hc"]] = idx

    def score_tal_hora0(hc):
        # Hora 0 = orden 0 en TIEMPOS_MEDICION.
        m = med_por_paciente.get(hc, {}).get(0)
        return (m["score_tal"] if m is not None else "") or ""

    archivo = os.path.join(current_app.root_path, "..", "oafcare_pacientes.csv")

    with open(archivo, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)

        def fila(*celdas):
            writer.writerow([_cs(c) for c in celdas])

        # --- Índice resumen (una fila por paciente, para filtrar por fechas) ---
        fila("RESUMEN — un renglón por paciente (para filtrar por inicio/fin de OAF)")
        fila("HC", "Nombre", "Sexo", "Sala de derivación",
             "Inicio OAF", "Fin OAF", "Score de TAL (Hora 0)", "Resultado")
        for p in pacientes:
            fila(p["hc"], p["nombre"], p["sexo"] or "", p["sala_derivacion"] or "",
                 _fecha_hora(p["fecha_inicio_oaf"], p["hora_inicio_oaf"]),
                 _fecha_hora(p["fecha_fin_oaf"], p["hora_fin_oaf"]),
                 score_tal_hora0(p["hc"]),
                 p["resultado_oaf"] or "")
        fila()
        fila()

        # --- Detalle por paciente (bloques, orden ascendente de HC) ---
        # Antes y después del cuadro de monitoreo los datos van EN COLUMNAS:
        # una fila de encabezados y debajo una fila de valores.
        for p in pacientes:
            fila("=" * 60)
            fila("PACIENTE " + str(p["hc"]), p["nombre"] or "")
            fila()

            fila("— Datos e inicio de OAF —")
            fila("HC", "Nombre y apellido", "Sexo", "Peso (Kg)", "Edad",
                 "Sala de derivación", "Diagnóstico", "Fecha de inicio de OAF",
                 "Hora de inicio de OAF", "Fecha de inicio de alimentación",
                 "Soporte previo al inicio de OAF", "Lugar de inicio de OAF")
            fila(p["hc"], p["nombre"] or "", p["sexo"] or "", p["peso"] or "",
                 formato_edad(p["edad"]), p["sala_derivacion"] or "",
                 p["diagnostico"] or "", p["fecha_inicio_oaf"] or "",
                 p["hora_inicio_oaf"] or "", p["fecha_inicio_alimentacion"] or "",
                 p["soporte_previo_oaf"] or "", p["lugar_inicio_oaf"] or "")
            fila()

            fila("— Virus —")
            fila(*[label for _, label in VIRUS_PANEL], "Otro / Detalle")
            fila(*[(p["virus_" + clave] or "") for clave, _ in VIRUS_PANEL],
                 p["virus_otro_detalle"] or "")
            fila()

            fila("— Comorbilidades y complicaciones —")
            fila("Comorbilidades", "Complicaciones")
            fila(p["comorbilidades"] or "", p["complicaciones"] or "")
            fila()

            # --- Cuadro de monitoreo: tiempos en filas, parámetros en columnas ---
            fila("— Monitoreo —")
            fila("Tiempo", *[label for _, label in PARAMETROS_MEDICION])
            idx = med_por_paciente.get(p["hc"], {})
            for orden, (_, tlabel) in enumerate(TIEMPOS_MEDICION):
                m = idx.get(orden)
                valores = [(m[pk] if m is not None else "") or "" for pk, _ in PARAMETROS_MEDICION]
                fila(tlabel, *valores)
            fila()

            fila("— Resultados —")
            fila("Fecha de fin de OAF", "Hora de fin de OAF", "Resultado")
            fila(p["fecha_fin_oaf"] or "", p["hora_fin_oaf"] or "", p["resultado_oaf"] or "")

            fila()
            fila()

    return send_file(archivo, as_attachment=True)


# ------------------ DASHBOARD ------------------

@charts_bp.route("/dashboard")
@login_required
def dashboard():
    desde = request.args.get("desde", "")
    hasta = request.args.get("hasta", "")
    t = int(time.time())
    return render_template(
        "charts/dashboard.html",
        desde=desde, hasta=hasta, t=t,
        flujo_data=_flujo_salas_data(),
        score_dist=_score_tal_hora0_dist(),
    )


def _score_tal_hora0_dist():
    """Distribución de pacientes por Score de TAL en la Hora 0 (orden 0).

    Devuelve una fila por cada score 0..12 con la cantidad de pacientes y su
    porcentaje sobre el total. Se cuenta un paciente por cada score entero en
    el rango 0–12; valores fuera de rango, no numéricos o vacíos se ignoran."""
    db = get_db()
    filas = db.execute(
        "SELECT score_tal FROM mediciones_oaf WHERE orden = 0"
    ).fetchall()

    conteo = {i: 0 for i in range(13)}  # 0..12
    for r in filas:
        try:
            f = float(str(r["score_tal"]).strip())
        except (ValueError, AttributeError, TypeError):
            continue
        if f.is_integer() and 0 <= f <= 12:
            conteo[int(f)] += 1

    total = sum(conteo.values())
    filas_out = [
        {"score": s, "cantidad": conteo[s],
         "pct": (conteo[s] / total * 100) if total else 0}
        for s in range(13)
    ]
    return {"filas": filas_out, "total": total}


def _flujo_salas_data():
    """Datos para el gráfico interactivo de flujo de pacientes:
    lugar de derivación (sala_derivacion) -> sala donde está (lugar_inicio_oaf).

    A la IZQUIERDA se muestran SIEMPRE todas las salas de derivación posibles
    (SALAS_DERIVACION) y a la DERECHA todas las salas de destino posibles
    (LUGARES_INICIO), tengan o no datos. Las flechas (flujos) se arman solas a
    partir de los pacientes cargados. Si algún paciente tiene un valor legacy
    fuera de esas listas, igual se agrega como nodo para no perder su flujo."""
    db = get_db()
    filas = db.execute(
        "SELECT sala_derivacion, lugar_inicio_oaf, COUNT(*) AS n FROM pacientes "
        "WHERE sala_derivacion IS NOT NULL AND sala_derivacion != '' "
        "AND lugar_inicio_oaf IS NOT NULL AND lugar_inicio_oaf != '' "
        "GROUP BY sala_derivacion, lugar_inicio_oaf"
    ).fetchall()

    origenes = list(SALAS_DERIVACION)
    destinos = list(LUGARES_INICIO)
    flujos = []
    for r in filas:
        origen, destino, n = r["sala_derivacion"], r["lugar_inicio_oaf"], r["n"]
        if origen not in origenes:
            origenes.append(origen)
        if destino not in destinos:
            destinos.append(destino)
        flujos.append({"origen": origen, "destino": destino, "n": n})

    return {
        "origenes": origenes,
        "destinos": destinos,
        "flujos": flujos,
    }

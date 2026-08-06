"""Formulario de carga de una investigación, apartado por apartado.

Acá viven las opciones fijas de cada pregunta, la lista de columnas de la tabla
`estudios` y los parsers que leen el `request.form`. Está pensado para crecer:
cada apartado nuevo agrega sus constantes, sus columnas a ESTUDIO_COLUMNAS y su
lectura en `estudio_desde_form`.

Cómo agregar una pregunta:
  1. Si tiene opciones fijas, definí la lista acá.
  2. Agregá su columna a ESTUDIO_COLUMNAS (el CREATE TABLE y la migración de
     `database.py` la toman de esta lista, no hay que tocar SQL).
  3. Leela en `estudio_desde_form`.
  4. Mostrala en el template del apartado y, si va en la vista de repositorio,
     agregala a GRUPOS_REPOSITORIO en utils/repositorio.py.
"""

# ---------------------------------------------------------------------------
# Apartado "Sobre el estudio"
# ---------------------------------------------------------------------------

# ¿De dónde se obtendrán los datos del estudio? (selección única)
FUENTES_DATOS = [
    "De pacientes, mediante mediciones, evaluaciones o procedimientos "
    "realizados específicamente para el estudio.",
    "De historias clínicas o registros existentes.",
    "De ambas fuentes: pacientes + historias clínicas/registros existentes",
    "De otras fuentes (especificar)",
]

# La única opción que habilita el campo de texto libre `fuente_datos_otra`.
# El JS del formulario muestra/oculta ese campo comparando contra este valor.
FUENTE_DATOS_OTRA = FUENTES_DATOS[3]

# ¿Cuál es la temporalidad del estudio? (selección única)
TEMPORALIDADES = [
    "Prospectivo",
    "Retrospectivo",
    "Ambispectivo",
    "No aplica",
]


# ---------------------------------------------------------------------------
# Columnas de la tabla `estudios`
# ---------------------------------------------------------------------------
# Orden = orden de los apartados. `database.py` arma el CREATE TABLE y las
# migraciones desde esta lista: agregar una columna acá alcanza para que exista
# en SQLite y en Postgres, en bases nuevas y en bases ya cargadas.
ESTUDIO_COLUMNAS = [
    # Apartado 1: sobre el estudio
    "titulo",
    "tema",
    "fuente_datos",
    "fuente_datos_otra",
    "temporalidad",
]


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _opcion_valida(valor, opciones) -> str:
    """Devuelve el valor solo si es una de las opciones; si no, cadena vacía.

    Evita que llegue a la base cualquier cosa mandada a mano en el POST.
    """
    valor = (valor or "").strip()
    return valor if valor in opciones else ""


def fuente_datos_desde_form(data) -> dict:
    """Lee la fuente de datos y su detalle libre.

    El detalle solo se conserva si la opción elegida es la de "otras fuentes":
    así no queda texto colgado si el usuario escribe algo y después cambia la
    opción.
    """
    fuente = _opcion_valida(data.get("fuente_datos"), FUENTES_DATOS)
    otra = (data.get("fuente_datos_otra") or "").strip()

    return {
        "fuente_datos": fuente,
        "fuente_datos_otra": otra if fuente == FUENTE_DATOS_OTRA else "",
    }


def temporalidad_desde_form(data) -> str:
    return _opcion_valida(data.get("temporalidad"), TEMPORALIDADES)


def estudio_desde_form(data) -> dict:
    """Lee todo el formulario -> dict con claves = ESTUDIO_COLUMNAS.

    Devuelve siempre todas las claves (vacías si no vinieron), así el INSERT y
    el UPDATE se arman desde la misma lista de columnas.
    """
    return {
        "titulo": (data.get("titulo") or "").strip(),
        "tema": (data.get("tema") or "").strip(),
        **fuente_datos_desde_form(data),
        "temporalidad": temporalidad_desde_form(data),
    }

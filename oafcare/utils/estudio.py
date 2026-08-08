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

import re

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
# Apartado "Investigadores"
# ---------------------------------------------------------------------------

# ¿Participan investigadores de otras instituciones? (selección única)
OTRAS_INSTITUCIONES = ["Sí", "No"]

# La opción que habilita el campo de texto libre `instituciones_detalle`.
# El JS del formulario muestra/oculta ese campo comparando contra este valor.
OTRAS_INSTITUCIONES_SI = OTRAS_INSTITUCIONES[0]


# ---------------------------------------------------------------------------
# Apartado "Estado de la investigación"
# ---------------------------------------------------------------------------

# Estado actual de la investigación (selección única). El orden es el del
# recorrido real de un estudio: del protocolo a la publicación, y al final los
# dos desenlaces que lo interrumpen.
ESTADOS_INVESTIGACION = [
    "Protocolo en elaboración",
    "Protocolo terminado",
    "Protocolo aprobado",
    "Reclutamiento / recolección de datos",
    "Análisis de datos",
    "Manuscrito en elaboración",
    "En revisión en revista",
    "Publicado",
    "Suspendido",
    "Finalizado sin publicar",
]

# La opción que habilita el campo `publicacion_url`, donde va la dirección en
# la que se puede leer el artículo. El JS del formulario muestra/oculta ese
# campo comparando contra este valor.
ESTADO_PUBLICADO = ESTADOS_INVESTIGACION[7]


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
    # Apartado 2: investigadores
    "director",
    "investigadores",
    "telefono_contacto",
    "email_contacto",
    "otras_instituciones",
    "instituciones_detalle",
    # Apartado 3: estado de la investigación
    "estado_actual",
    "publicacion_url",
]


# Campos sin los que una investigación no se puede guardar. El título la
# identifica; el teléfono y el mail son el contacto para llegar al equipo, y un
# registro sin forma de contactar a nadie no sirve para nada.
# (clave de columna, cómo nombrarla en el mensaje de error)
CAMPOS_OBLIGATORIOS = [
    ("titulo", "el título del estudio"),
    ("telefono_contacto", "el teléfono de contacto"),
    ("email_contacto", "el mail de contacto"),
]


def faltantes(datos: dict) -> list:
    """Nombres de los campos obligatorios que vinieron vacíos."""
    return [nombre for col, nombre in CAMPOS_OBLIGATORIOS if not datos.get(col)]


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


def instituciones_desde_form(data) -> dict:
    """Lee si participan otras instituciones y, si es que sí, cuáles.

    El detalle solo se conserva cuando la respuesta es "Sí": si alguien escribe
    las instituciones y después cambia a "No", no queda texto colgado. Misma
    regla que `fuente_datos_desde_form`.
    """
    participan = _opcion_valida(data.get("otras_instituciones"), OTRAS_INSTITUCIONES)
    detalle = (data.get("instituciones_detalle") or "").strip()

    return {
        "otras_instituciones": participan,
        "instituciones_detalle": detalle if participan == OTRAS_INSTITUCIONES_SI else "",
    }


# Un DOI suelto: es lo que suele estar a mano en una publicación, y pegado tal
# cual no es una dirección que el navegador pueda abrir.
_DOI = re.compile(r"^(?:doi:\s*)?(10\.\d{4,9}/\S+)$", re.IGNORECASE)

# Esquemas que se pueden poner en un href sin riesgo. Cualquier otro
# (javascript:, data:) se descarta: el valor lo escribe una persona y termina
# en un enlace que van a tocar los demás.
_ESQUEMAS_OK = ("http://", "https://")


def normalizar_url(valor) -> str:
    """Deja la dirección de la publicación lista para usar en un enlace.

    Acepta lo que la gente tiene a mano y lo vuelve abrible:
      - `revista.com/articulo`  -> `https://revista.com/articulo`
      - `10.1016/j.jpeds.2024`  -> `https://doi.org/10.1016/j.jpeds.2024`
      - `https://…`             -> tal cual

    Devuelve cadena vacía si no se puede convertir en algo seguro, así nunca
    llega a un `href` un esquema que ejecute código.
    """
    valor = (valor or "").strip()
    if not valor:
        return ""

    doi = _DOI.match(valor)
    if doi:
        return f"https://doi.org/{doi.group(1)}"

    if valor.lower().startswith(_ESQUEMAS_OK):
        return valor

    # Sin esquema: se asume web. Con cualquier otro esquema, se descarta.
    if "://" in valor or valor.lower().startswith(("javascript:", "data:", "vbscript:")):
        return ""

    return f"https://{valor}"


def estado_desde_form(data) -> dict:
    """Lee el estado actual y, si está publicado, dónde está publicado.

    La dirección solo se conserva cuando el estado es "Publicado": misma regla
    que `fuente_datos_desde_form` e `instituciones_desde_form`, para que no
    quede un enlace colgado si el estado vuelve para atrás.
    """
    estado = _opcion_valida(data.get("estado_actual"), ESTADOS_INVESTIGACION)
    url = normalizar_url(data.get("publicacion_url"))

    return {
        "estado_actual": estado,
        "publicacion_url": url if estado == ESTADO_PUBLICADO else "",
    }


def estudio_desde_form(data) -> dict:
    """Lee todo el formulario -> dict con claves = ESTUDIO_COLUMNAS.

    Devuelve siempre todas las claves (vacías si no vinieron), así el INSERT y
    el UPDATE se arman desde la misma lista de columnas.
    """
    return {
        # Apartado 1: sobre el estudio
        "titulo": (data.get("titulo") or "").strip(),
        "tema": (data.get("tema") or "").strip(),
        **fuente_datos_desde_form(data),
        "temporalidad": temporalidad_desde_form(data),
        # Apartado 2: investigadores
        "director": (data.get("director") or "").strip(),
        "investigadores": (data.get("investigadores") or "").strip(),
        "telefono_contacto": (data.get("telefono_contacto") or "").strip(),
        # Se guarda tal cual se escribió (solo sin espacios de sobra): el
        # formato lo valida el navegador con type="email". Acá no se descarta
        # nada, para no perder un contacto por una regla nuestra de más.
        "email_contacto": (data.get("email_contacto") or "").strip(),
        **instituciones_desde_form(data),
        # Apartado 3: estado de la investigación
        **estado_desde_form(data),
    }

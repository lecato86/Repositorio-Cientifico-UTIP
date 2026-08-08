"""Material descargable y trámite de evaluación de la pantalla "Cómo comenzar".

Los PDFs no van hardcodeados: se listan leyendo `static/docs/`, así para publicar
un documento nuevo alcanza con copiar el archivo en la carpeta del paso que
corresponda, sin tocar código ni plantillas.
"""

import os
from flask import current_app

# Subcarpeta de `static/` donde viven los PDFs de la guía.
CARPETA_DOCS = "docs"

# Formulario de la Comisión de Investigación: con esto se inicia el trámite.
FORMULARIO_COMISION = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSfFkdC6BNF0Pc5ZeCkVm7Ev43YC2kU4nz9Slx-imxp0f6X0ug/viewform"
)

# El trámite ante la Comisión, en el orden en que se hace. La plantilla los
# recorre y numera sola, así que el número que se muestra sale de esta lista:
# si se agrega un paso en el medio, la referencia "Paso 3" del texto anterior
# hay que ajustarla a mano.
#   `carpeta`     subcarpeta de static/docs/ con los PDFs del paso (None si no tiene)
#   `formulario`  link con el que se cierra el paso (None si no tiene)
PASOS_TRAMITE = [
    {
        "titulo": "Escritura del trabajo final",
        "texto": (
            "Antes de enviar tu trabajo de investigación / Publicación / Póster / "
            "Otros, revisá que cumpla con los siguientes lineamientos "
            "(si corresponde)."
        ),
        "carpeta": "1-escritura-del-trabajo-final",
        "formulario": None,
    },
    {
        "titulo": "Notas de solicitud",
        "texto": (
            "Una vez verificados los documentos anteriores, se deben completar "
            "digitalmente las siguientes notas para adjuntarlas en el formulario "
            "del Paso 3."
        ),
        "carpeta": "2-notas-de-solicitud",
        "formulario": None,
    },
    {
        "titulo": "Solicitud de evaluación",
        "texto": (
            "Para iniciar el trámite de solicitud de evaluación debe completar "
            "el siguiente formulario."
        ),
        "carpeta": None,
        "formulario": FORMULARIO_COMISION,
    },
]


def _titulo_desde_archivo(nombre: str) -> str:
    """'01_Guia-de-ingreso.pdf' -> '01 Guia de ingreso'."""
    base = os.path.splitext(nombre)[0]
    return base.replace("_", " ").replace("-", " ").strip()


def _pdfs_de(subcarpeta: str = "") -> list:
    """PDFs de `static/docs/<subcarpeta>/`, ordenados por nombre de archivo.

    Devuelve [{'archivo', 'titulo', 'kb'}], donde `archivo` es la ruta relativa
    a `static/` (lista para `url_for('static')`). Si la carpeta todavía no
    existe, devuelve lista vacía en vez de fallar.
    """
    relativa = f"{CARPETA_DOCS}/{subcarpeta}" if subcarpeta else CARPETA_DOCS
    carpeta = os.path.join(current_app.static_folder, *relativa.split("/"))
    if not os.path.isdir(carpeta):
        return []

    documentos = []
    for nombre in sorted(os.listdir(carpeta)):
        if not nombre.lower().endswith(".pdf"):
            continue
        ruta = os.path.join(carpeta, nombre)
        documentos.append({
            "archivo": f"{relativa}/{nombre}",
            "titulo": _titulo_desde_archivo(nombre),
            "kb": max(1, round(os.path.getsize(ruta) / 1024)),
        })

    return documentos


def pasos_tramite() -> list:
    """`PASOS_TRAMITE` con los PDFs de cada paso ya resueltos."""
    return [
        {**paso, "documentos": _pdfs_de(paso["carpeta"]) if paso["carpeta"] else []}
        for paso in PASOS_TRAMITE
    ]


def documentos_disponibles() -> list:
    """PDFs sueltos en `static/docs/` (los que no son de ningún paso).

    Sirve para publicar material de consulta que no forma parte del trámite:
    se copia el PDF en la raíz de la carpeta y aparece en "Otros documentos".
    """
    return _pdfs_de()

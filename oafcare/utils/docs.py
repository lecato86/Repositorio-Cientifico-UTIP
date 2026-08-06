"""Material descargable de la pantalla "Cómo comenzar".

Los PDFs no van hardcodeados: se listan leyendo la carpeta `static/docs/`, así
para publicar un documento nuevo alcanza con copiar el archivo ahí, sin tocar
código ni plantillas.
"""

import os
from flask import current_app

# Subcarpeta de `static/` donde viven los PDFs de la guía.
CARPETA_DOCS = "docs"


def _titulo_desde_archivo(nombre: str) -> str:
    """'01_Guia-de-ingreso.pdf' -> '01 Guia de ingreso'."""
    base = os.path.splitext(nombre)[0]
    return base.replace("_", " ").replace("-", " ").strip()


def documentos_disponibles() -> list:
    """Devuelve [{'archivo', 'titulo', 'kb'}] con los PDFs de static/docs/.

    `archivo` es la ruta relativa a `static/` (lista para `url_for('static')`).
    Si la carpeta todavía no existe, devuelve lista vacía en vez de fallar.
    """
    carpeta = os.path.join(current_app.static_folder, CARPETA_DOCS)
    if not os.path.isdir(carpeta):
        return []

    documentos = []
    for nombre in sorted(os.listdir(carpeta)):
        if not nombre.lower().endswith(".pdf"):
            continue
        ruta = os.path.join(carpeta, nombre)
        documentos.append({
            "archivo": f"{CARPETA_DOCS}/{nombre}",
            "titulo": _titulo_desde_archivo(nombre),
            "kb": max(1, round(os.path.getsize(ruta) / 1024)),
        })

    return documentos

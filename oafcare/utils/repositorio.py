"""Especificación de la vista "Consultar repositorio".

Define en un solo lugar qué campos de la tabla `estudios` se muestran en la
visualización completa de la base, con qué etiqueta y agrupados en qué bloque
del encabezado. Al agregar una pregunta al formulario (ver ESTUDIO_COLUMNAS en
utils/estudio.py) agregala también acá para que aparezca en la vista.
"""

# Bloques del encabezado: (título del grupo, [(clave de columna, etiqueta), ...]).
# Las claves son columnas de `estudios`.
GRUPOS_REPOSITORIO = [
    ("Sobre el estudio", [
        ("titulo", "Título del estudio"),
        ("tema", "Tema a estudiar"),
        ("fuente_datos", "Origen de los datos"),
        ("fuente_datos_otra", "Otra fuente (detalle)"),
        ("temporalidad", "Temporalidad"),
    ]),
    ("Investigadores", [
        ("director", "Director"),
        ("investigadores", "Investigadores"),
        ("telefono_contacto", "Teléfono de contacto"),
        ("email_contacto", "Mail de contacto"),
        ("otras_instituciones", "¿Otras instituciones?"),
        ("instituciones_detalle", "Qué instituciones"),
    ]),
    ("Estado", [
        ("estado_actual", "Estado actual"),
    ]),
    ("Registro", [
        ("creado_por", "Cargado por"),
        ("creado_en", "Fecha de carga"),
        ("actualizado_en", "Última modificación"),
    ]),
]

# Lista plana de columnas, en el mismo orden que los grupos.
COLUMNAS_REPOSITORIO = [
    col for _, columnas in GRUPOS_REPOSITORIO for col in columnas
]

# Columnas que la vista fija a la izquierda al scrollear en horizontal.
COLUMNAS_FIJAS = ("titulo",)

# Columnas cuyo texto puede ser largo: la vista las deja partir en varias
# líneas en vez de forzar el scroll horizontal.
COLUMNAS_LARGAS = (
    "tema", "fuente_datos", "fuente_datos_otra",
    "investigadores", "instituciones_detalle", "estado_actual",
)

# Campos que tienen que estar cargados para considerar completa una
# investigación. Quedan afuera los que solo aplican a una opción puntual
# (`fuente_datos_otra`, `instituciones_detalle`).
CAMPOS_REQUERIDOS = (
    "titulo", "tema", "fuente_datos", "temporalidad",
    "director", "investigadores", "telefono_contacto", "email_contacto",
    "otras_instituciones", "estado_actual",
)


def resumen_repositorio(filas) -> dict:
    """Contadores para la banda superior de la vista de repositorio."""
    total = len(filas)
    completas = sum(
        1 for f in filas
        if all((f[campo] or "").strip() for campo in CAMPOS_REQUERIDOS)
    )
    autores = {
        (f["creado_por"] or "").strip() for f in filas if (f["creado_por"] or "").strip()
    }

    return {
        "total": total,
        "completas": completas,
        "incompletas": total - completas,
        "autores": len(autores),
    }

"""Datos y parsers del formulario de ingreso de paciente.

Centraliza las opciones fijas del formulario (sexo, sala de derivación,
panel de virus) y las funciones que leen esos campos desde el `request.form`.
Pensado para ir creciendo: cuando se agreguen más parámetros al ingreso,
sus constantes y parsers van acá.
"""

# Opciones de sexo (el formulario obliga a elegir una).
SEXOS = ["F", "M", "Otro"]

# Salas desde las que puede venir derivado el paciente al ingreso.
# OJO: es una lista propia, distinta de utils.soporte.SALAS (las salas de
# internación donde se hace el seguimiento diario).
SALAS_DERIVACION = [
    "Guardia Central",
    "SIP 200",
    "SIP 400",
    "SIP 500",
    "SIP 600",
    "UCI 100",
    "UCI 300",
    "UTI",
    "UCO",
]

# Estados posibles de cada virus del panel (selección única por virus).
ESTADOS_VIRUS = [
    "Positivo",
    "Negativo",
    "Pendiente",
    "No Solicitado",
    "No sabe/no contesta",
]

# Panel de virus: (clave interna / nombre de columna, etiqueta visible).
# La clave se usa para el name del radio (virus_<clave>) y para la columna
# en la tabla pacientes (virus_<clave>).
VIRUS_PANEL = [
    ("vsr", "VSR"),
    ("adenovirus", "Adenovirus"),
    ("influenza", "Influenza"),
    ("parainfluenza", "Parainfluenza"),
    ("metapneumovirus", "Metapneumovirus"),
    ("sarscov2", "SARS-CoV-2"),
    ("picornavirus", "Picornavirus"),
    ("otros", "Otros virus"),
]

# Nombres de columna que genera el panel de virus en la tabla pacientes.
VIRUS_COLUMNAS = [f"virus_{clave}" for clave, _ in VIRUS_PANEL] + ["virus_otro_detalle"]

# Comorbilidades: selección MÚLTIPLE (checkbox, no exclusiva). Se guardan en
# una sola columna de texto (comorbilidades) separadas por ", ".
COMORBILIDADES = [
    "Cardiovascular",
    "Respiratoria",
    "Metabólica",
    "Inmunológica",
    "Neurológica",
    "Enfermedad Maligna",
    "Renal o Urológica",
    "Gastrointestinal",
    "Prematurez",
    "Congénita o Genética",
    "Dependencia de Tecnología",
    "Transplante",
    "Otros",
]


def sexo_desde_form(data) -> str:
    sexo = (data.get("sexo") or "").strip()
    return sexo if sexo in SEXOS else ""


def sala_derivacion_desde_form(data) -> str:
    sala = (data.get("sala_derivacion") or "").strip()
    return sala if sala in SALAS_DERIVACION else ""


def peso_desde_form(data) -> str:
    """Peso en Kg. Se guarda como texto para admitir decimales y vacío."""
    return (data.get("peso") or "").strip()


def virus_desde_form(data) -> dict:
    """Devuelve {'virus_vsr': 'Positivo', ..., 'virus_otro_detalle': '...'}.

    Cada virus admite un solo estado (radio). Un estado inválido o ausente
    queda como cadena vacía. `virus_otro_detalle` es texto libre.
    """
    resultado = {}
    for clave, _ in VIRUS_PANEL:
        estado = (data.get(f"virus_{clave}") or "").strip()
        resultado[f"virus_{clave}"] = estado if estado in ESTADOS_VIRUS else ""
    resultado["virus_otro_detalle"] = (data.get("virus_otro_detalle") or "").strip()
    return resultado


# Soporte respiratorio previo al inicio de OAF (selección única / radio).
SOPORTES_PREVIOS = [
    "Aire ambiente",
    "Cánula nasal de bajo flujo",
    "Máscara simple",
    "Máscara con reservorio",
    "Máscara de Venturi",
    "Halo cefálico",
    "Cánula nasal de alto flujo (en caso de derivación)",
]

# Lugar donde se inició la OAF (selección única / radio).
# Mismas salas que SALAS_DERIVACION (origen y destino usan el mismo listado).
LUGARES_INICIO = [
    "Guardia Central",
    "SIP 200",
    "SIP 400",
    "SIP 500",
    "SIP 600",
    "UCI 100",
    "UCI 300",
    "UTI",
    "UCO",
]

# Complicaciones (selección MÚLTIPLE / checkbox).
COMPLICACIONES = [
    "Lesiones de mucosa nasal",
    "Lesiones de piel de la cara",
    "Distensión abdominal",
    "Atelectasia",
    "Enfisema subcutáneo",
    "Neumotórax",
    "Desconexión del circuito",
    "Mal funcionamiento del equipo",
]

# Resultado final del soporte de OAF (selección única / radio).
RESULTADOS_OAF = [
    "Éxito",
    "Fracaso",
    "Se desconoce (derivado con OAF)",
    "Pérdida de dato",
]

# Tabla de monitoreo: (clave para el name del input, etiqueta de la fila).
TIEMPOS_MEDICION = [
    ("t0", "Hora 0"),
    ("t30", "30 minutos"),
    ("t60", "60 minutos"),
    ("t90", "90 minutos"),
    ("t2h", "2 horas"),
    ("t4h", "4 horas"),
    ("t8h", "8 horas"),
    ("t12h", "12 horas"),
    ("t24h", "24 horas"),
]

# Columnas de la tabla de monitoreo: (clave = columna en mediciones_oaf, etiqueta).
PARAMETROS_MEDICION = [
    ("fc", "Frecuencia cardíaca"),
    ("fr", "Frecuencia respiratoria"),
    ("sato2", "Saturación de oxígeno"),
    ("score_tal", "Score de TAL"),
    ("fio2", "Fracción inhalada de Oxígeno (%)"),
    ("flujo", "Flujo en litros/min"),
]


def soporte_previo_desde_form(data) -> str:
    valor = (data.get("soporte_previo_oaf") or "").strip()
    return valor if valor in SOPORTES_PREVIOS else ""


def lugar_inicio_desde_form(data) -> str:
    valor = (data.get("lugar_inicio_oaf") or "").strip()
    return valor if valor in LUGARES_INICIO else ""


def resultado_desde_form(data) -> str:
    valor = (data.get("resultado_oaf") or "").strip()
    return valor if valor in RESULTADOS_OAF else ""


def complicaciones_desde_form(data) -> str:
    marcadas = set(data.getlist("complicacion"))
    return ", ".join(c for c in COMPLICACIONES if c in marcadas)


def complicaciones_seleccionadas(valor) -> list:
    if not valor:
        return []
    partes = {p.strip() for p in str(valor).split(",")}
    return [c for c in COMPLICACIONES if c in partes]


def mediciones_desde_form(data) -> list:
    """Lee la tabla de monitoreo. Devuelve una fila por tiempo (9 filas).

    Cada fila: {'orden': int, 'tiempo': etiqueta, 'fc': str, ...}. Los valores
    van como texto (admiten vacío y decimales). El filtrado de filas vacías lo
    hace el modelo al guardar.
    """
    filas = []
    for orden, (tk, tl) in enumerate(TIEMPOS_MEDICION):
        fila = {"orden": orden, "tiempo": tl}
        for pk, _ in PARAMETROS_MEDICION:
            fila[pk] = (data.get(f"med_{pk}_{tk}") or "").strip()
        filas.append(fila)
    return filas


def mediciones_valores(filas) -> dict:
    """Arma el dict {'med_fc_t0': '150', ...} para repoblar la tabla al editar.

    `filas` son rows de mediciones_oaf (con `orden` y las columnas de parámetros).
    El `orden` mapea a la clave de tiempo en TIEMPOS_MEDICION.
    """
    claves_tiempo = [tk for tk, _ in TIEMPOS_MEDICION]
    valores = {}
    for f in filas:
        try:
            orden = int(f["orden"])
        except (TypeError, ValueError, KeyError):
            continue
        if not (0 <= orden < len(claves_tiempo)):
            continue
        tk = claves_tiempo[orden]
        for pk, _ in PARAMETROS_MEDICION:
            v = f[pk]
            if v not in (None, ""):
                valores[f"med_{pk}_{tk}"] = v
    return valores


def comorbilidades_desde_form(data) -> str:
    """Lee las comorbilidades tildadas (checkbox múltiple) y las une con ", ".

    Conserva el orden de COMORBILIDADES y descarta valores no válidos.
    """
    marcadas = set(data.getlist("comorbilidad"))
    return ", ".join(c for c in COMORBILIDADES if c in marcadas)


def comorbilidades_seleccionadas(valor) -> list:
    """Convierte el texto guardado en lista, para repoblar los checkboxes."""
    if not valor:
        return []
    partes = {p.strip() for p in str(valor).split(",")}
    return [c for c in COMORBILIDADES if c in partes]


def virus_seleccionados(paciente) -> dict:
    """Extrae de un row de paciente los estados de virus para repoblar el form.

    Devuelve {'vsr': 'Positivo', ...} (claves sin prefijo, para el macro).
    """
    valores = {}
    for clave, _ in VIRUS_PANEL:
        try:
            valores[clave] = paciente[f"virus_{clave}"] or ""
        except (KeyError, IndexError, TypeError):
            valores[clave] = ""
    return valores

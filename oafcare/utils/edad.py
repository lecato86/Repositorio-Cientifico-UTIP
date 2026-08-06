def parse_edad_meses(valor, asumir_anios_legacy=False):
    if valor is None:
        return None

    texto = str(valor).strip()
    if not texto:
        return None

    try:
        numero = int(float(texto.replace(",", ".")))
        if asumir_anios_legacy and 0 <= numero <= 120:
            return numero * 12
        return max(numero, 0)
    except ValueError:
        pass

    partes = texto.lower().replace("años", "anio").replace("año", "anio")
    partes = partes.replace("meses", "mes").replace("mes", "mes")
    anios = 0
    meses = 0
    tokens = partes.replace("y", " ").split()
    for i, token in enumerate(tokens):
        try:
            numero = int(float(token.replace(",", ".")))
        except ValueError:
            continue
        siguiente = tokens[i + 1] if i + 1 < len(tokens) else ""
        if siguiente.startswith("anio"):
            anios = numero
        elif siguiente.startswith("mes"):
            meses = numero

    if anios or meses:
        return (anios * 12) + meses
    return None

def edad_meses_desde_form(data):
    anios = int(data.get("edad_anios") or 0)
    meses = int(data.get("edad_meses_extra") or 0)
    anios = min(max(anios, 0), 120)
    meses = min(max(meses, 0), 11)
    return (anios * 12) + meses

def edad_partes(valor):
    total = parse_edad_meses(valor) or 0
    return total // 12, total % 12

def formato_edad(valor):
    total = parse_edad_meses(valor)
    if total is None:
        return ""
    anios, meses = total // 12, total % 12
    texto_anios = f"{anios} año" if anios == 1 else f"{anios} años"
    texto_meses = f"{meses} mes" if meses == 1 else f"{meses} meses"
    if anios and meses:
        return f"{texto_anios} y {texto_meses}"
    if anios:
        return texto_anios
    return texto_meses

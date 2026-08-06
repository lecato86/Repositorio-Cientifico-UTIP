MUESTRAS = sorted(["AGV", "PCR", "CULTIVO", "FILMARRAY"])


def muestras_desde_form(data) -> str:
    seleccionadas = [
        muestra.strip().upper()
        for muestra in data.getlist("muestra")
        if muestra.strip().upper() in MUESTRAS
    ]
    return ", ".join(sorted(set(seleccionadas)))


def muestras_seleccionadas(valor) -> list[str]:
    if not valor:
        return []
    return [
        muestra.strip().upper()
        for muestra in str(valor).split(",")
        if muestra.strip().upper() in MUESTRAS
    ]

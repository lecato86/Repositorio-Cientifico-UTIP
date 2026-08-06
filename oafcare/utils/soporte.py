SALAS = [
    "Sala 1",
    "Sala 2",
    "FUELLE",
    "UEPE",
    "UTI 100",
    "UCI 300",
    "UCI 100",
    "SIP400",
    "SIP 500",
    "SIP 600",
    "UCO",
    "Consultorio Externo",
]

SOPORTES = [
    "ARM",
    "VNI",
    "OAF",
    "MR",
    "VENTURI",
    "CN",
    "AA",
]

SOPORTE_NIVELES = {
    "ARM": 1,
    "VNI": 2,
    "OAF": 3,
    "MR": 4,
    "VENTURI": 5,
    "CN": 6,
    "AA": 7,
}

def soporte_desde_form(data):
    soporte = data.get("soporte", "").strip().upper()
    return soporte if soporte in SOPORTES else ""

def normalizar_soporte(valor):
    soporte = (valor or "").strip().upper()
    return soporte if soporte in SOPORTE_NIVELES else ""

def soporte_en_fecha(eventos, fecha, fallback=""):
    resultado = fallback
    for evento in eventos:
        if evento["fecha"] <= fecha:
            resultado = evento["valor_nuevo"]
    return resultado

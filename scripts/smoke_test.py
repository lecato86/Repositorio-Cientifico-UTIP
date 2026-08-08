"""Prueba de humo: levanta la app contra una SQLite temporal, entra con nombre
+ DNI y recorre las pantallas del repositorio, incluyendo la carga, la edicion
y el control de que solo el autor puede modificar su trabajo."""

import os
import sys
import tempfile
import traceback

# Raiz del proyecto (este script vive en scripts/). El Python portable
# (distribucion embeddable) no la agrega sola a sys.path, asi que la ponemos a
# mano para poder importar `oafcare` y `config`.
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
db_fd, db_path = tempfile.mkstemp(suffix=".db")
os.close(db_fd)

os.environ["SECRET_KEY"] = "smoke-test-key"
os.environ["DATABASE"] = db_path
os.environ["DEBUG"] = "True"
os.environ["ADMIN_DNIS"] = "30123456"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("RENDER", None)

fallos = []


def check(nombre, condicion, detalle=""):
    estado = "OK  " if condicion else "FALLA"
    print(f"  [{estado}] {nombre}" + (f" -> {detalle}" if detalle and not condicion else ""))
    if not condicion:
        fallos.append(nombre)


try:
    from oafcare import create_app

    app = create_app()
    print("create_app() + init_db(): OK\n")

    ANA = {"nombre": "Ana Perez", "dni": "30.123.456"}      # admin (ADMIN_DNIS)
    BETO = {"nombre": "Beto Lopez", "dni": "27999888"}      # usuario comun

    with app.test_client() as c:
        # --- login sin contrasena: nombre y apellido + DNI ---
        print("Login:")
        r = c.post("/login", data={"nombre": "", "dni": ""}, follow_redirects=False)
        check("rechaza el form vacio", r.status_code == 200 and
              "Completá tu nombre" in r.get_data(as_text=True))
        r = c.post("/login", data={"nombre": "Ana Perez", "dni": "abc"})
        check("rechaza un DNI sin numeros", r.status_code == 200)

        r = c.post("/login", data=ANA, follow_redirects=False)
        check("login con nombre + DNI redirige", r.status_code == 302,
              f"status {r.status_code}")
        check("login lleva al inicio del repositorio",
              r.headers.get("Location", "").endswith("/"), r.headers.get("Location"))
        check("el nombre se muestra en la pagina",
              "Ana Perez" in c.get("/").get_data(as_text=True))

        # --- pantallas GET ---
        print("\nPantallas:")
        for ruta, esperado in [
            ("/", "Repositorio Cient"),
            ("/nueva-investigacion", "Sobre el estudio"),
            ("/repositorio", "Repositorio de investigaciones"),
            ("/modificar", "Modificar investigaci"),
            ("/como-comenzar", "Cómo comenzar"),
        ]:
            r = c.get(ruta)
            html = r.get_data(as_text=True)
            check(f"GET {ruta} 200", r.status_code == 200, f"status {r.status_code}")
            check(f"GET {ruta} contiene texto esperado", esperado in html, esperado)

        # --- el menu tiene las 4 opciones ---
        print("\nMenu de inicio:")
        html = c.get("/").get_data(as_text=True)
        for opcion in ["Cargar una investigación", "Consultar el repositorio",
                       "Modificar una investigación", "Cómo comenzar"]:
            check(f"opcion '{opcion}'", opcion in html)

        check("el titulo va en mayusculas",
              "REPOSITORIO CIENTÍFICO <span>UTIP</span>" in html)
        check("debajo del titulo no hay bajada",
              "Unidad de Terapia Intensiva" not in html)

        # Los acentos tienen que llegar bien al navegador: este archivo ya
        # estuvo guardado con la codificacion rota y en pantalla se leia
        # "CientÃ­fico". Se chequea en TODAS las pantallas mas abajo.
        check("el titulo no tiene caracteres rotos", "Ã" not in html)

        # --- el formulario tiene las 4 preguntas y sus opciones ---
        print("\nFormulario (apartado Sobre el estudio):")
        html = c.get("/nueva-investigacion").get_data(as_text=True)
        for campo in ['name="titulo"', 'name="tema"', 'name="fuente_datos"',
                      'name="fuente_datos_otra"', 'name="temporalidad"']:
            check(f"campo {campo}", campo in html)
        from oafcare.utils.estudio import FUENTES_DATOS, TEMPORALIDADES
        for opcion in FUENTES_DATOS:
            check(f"opcion fuente: {opcion[:38]}...", opcion in html)
        for opcion in TEMPORALIDADES:
            check(f"opcion temporalidad: {opcion}", opcion in html)

        # --- repositorio vacio ---
        print("\nRepositorio vacio:")
        html = c.get("/repositorio").get_data(as_text=True)
        check("muestra el estado vacio", "Todavía no hay investigaciones" in html)

        # --- guardar una investigacion ---
        print("\nGuardar investigacion:")
        r = c.post("/nueva-investigacion", data={
            "titulo": "Ventilacion no invasiva en bronquiolitis",
            "tema": "Fracaso de VNI en menores de 2 anios",
            "fuente_datos": FUENTES_DATOS[2],
            "fuente_datos_otra": "esto no deberia guardarse",
            "temporalidad": "Retrospectivo",
        })
        check("POST redirige al repositorio", r.status_code == 302, f"status {r.status_code}")
        check("redirige a /repositorio",
              r.headers.get("Location", "").endswith("/repositorio"),
              r.headers.get("Location"))

        html = c.get("/repositorio").get_data(as_text=True)
        check("la investigacion aparece en la tabla",
              "Ventilacion no invasiva en bronquiolitis" in html)
        check("guarda la temporalidad", "Retrospectivo" in html)
        check("guarda el usuario que cargo", "Ana Perez" in html)
        check("NO guarda el detalle de otra fuente (opcion no era 'otras')",
              "esto no deberia guardarse" not in html)

        # --- titulo obligatorio ---
        print("\nValidacion:")
        r = c.post("/nueva-investigacion", data={"titulo": "  ", "tema": "x"})
        check("rechaza titulo vacio con 400", r.status_code == 400, f"status {r.status_code}")

        # --- "otras fuentes" SI guarda el detalle ---
        r = c.post("/nueva-investigacion", data={
            "titulo": "Estudio con fuente externa",
            "tema": "Registro provincial",
            "fuente_datos": FUENTES_DATOS[3],
            "fuente_datos_otra": "Registro provincial de egresos",
            "temporalidad": "Prospectivo",
        })
        html = c.get("/repositorio").get_data(as_text=True)
        check("con 'otras fuentes' SI guarda el detalle",
              "Registro provincial de egresos" in html)

        # --- buscar por titulo: una sola coincidencia redirige a editar ---
        print("\nModificar por titulo:")
        r = c.get("/modificar?titulo=fuente+externa")
        check("una coincidencia redirige a editar", r.status_code == 302,
              f"status {r.status_code}")
        destino = r.headers.get("Location", "")
        check("redirige a /estudios/<id>/editar", "/editar" in destino, destino)

        r = c.get(destino)
        html = r.get_data(as_text=True)
        check("el formulario abre prellenado", r.status_code == 200)
        check("prellena el titulo", "Estudio con fuente externa" in html)
        check("prellena el detalle de otra fuente",
              "Registro provincial de egresos" in html)

        # --- buscar sin resultados ---
        r = c.get("/modificar?titulo=zzzzzz")
        check("sin resultados muestra el aviso",
              "No hay ninguna investigaci" in r.get_data(as_text=True))

        # --- actualizar ---
        estudio_id = destino.rstrip("/").split("/")[-2]
        r = c.post(f"/estudios/{estudio_id}/actualizar", data={
            "titulo": "Estudio con fuente externa (corregido)",
            "tema": "Registro provincial",
            "fuente_datos": FUENTES_DATOS[1],
            "fuente_datos_otra": "deberia borrarse al cambiar de opcion",
            "temporalidad": "Ambispectivo",
        })
        check("actualizar redirige", r.status_code == 302, f"status {r.status_code}")
        html = c.get("/repositorio").get_data(as_text=True)
        check("guarda el titulo corregido",
              "Estudio con fuente externa (corregido)" in html)
        check("guarda la temporalidad nueva", "Ambispectivo" in html)
        check("borra el detalle al cambiar de opcion",
              "deberia borrarse al cambiar de opcion" not in html)

        # --- otro usuario NO puede modificar lo ajeno ---
        print("\nPropiedad por DNI (otro usuario):")
        c.get("/logout")
        c.post("/login", data=BETO)

        r = c.get("/repositorio")
        html = r.get_data(as_text=True)
        check("SI puede consultar el repositorio", r.status_code == 200)
        check("ve la investigacion de la otra persona",
              "Estudio con fuente externa (corregido)" in html)
        check("NO le ofrece el boton Modificar", "btn-editar" not in html)

        r = c.get(f"/estudios/{estudio_id}/editar")
        html = r.get_data(as_text=True)
        check("editar lo ajeno da 403", r.status_code == 403, f"status {r.status_code}")
        check("muestra el cartel exacto",
              "SOLO EL USUARIO QUE CARGÓ ESTE TRABAJO PUEDE MODIFICARLO" in html)

        r = c.post(f"/estudios/{estudio_id}/actualizar", data={
            "titulo": "PISADO POR OTRO USUARIO", "tema": "x",
            "fuente_datos": FUENTES_DATOS[0], "temporalidad": "Retrospectivo",
        })
        check("POST de actualizar lo ajeno tambien da 403", r.status_code == 403,
              f"status {r.status_code}")
        html = c.get("/repositorio").get_data(as_text=True)
        check("el estudio ajeno quedo intacto", "PISADO POR OTRO USUARIO" not in html)

        r = c.get("/modificar?titulo=fuente+externa")
        html = r.get_data(as_text=True)
        check("la busqueda NO redirige a editar lo ajeno", r.status_code == 200,
              f"status {r.status_code}")
        check("la lista marca la investigacion como ajena", "inv-ajena" in html)

        # --- pero SI puede cargar lo suyo y editarlo ---
        print("\nEl mismo usuario SI edita lo suyo:")
        c.post("/nueva-investigacion", data={
            "titulo": "Estudio de Beto", "tema": "Sedacion",
            "fuente_datos": FUENTES_DATOS[0], "temporalidad": "Prospectivo",
        })
        r = c.get("/modificar?titulo=Estudio+de+Beto")
        check("una coincidencia propia redirige a editar", r.status_code == 302,
              f"status {r.status_code}")
        destino_beto = r.headers.get("Location", "")
        r = c.get(destino_beto)
        check("abre el formulario de lo propio", r.status_code == 200,
              f"status {r.status_code}")
        id_beto = destino_beto.rstrip("/").split("/")[-2]
        r = c.post(f"/estudios/{id_beto}/actualizar", data={
            "titulo": "Estudio de Beto (corregido)", "tema": "Sedacion",
            "fuente_datos": FUENTES_DATOS[0], "temporalidad": "Prospectivo",
        })
        check("guarda su propia edicion", r.status_code == 302, f"status {r.status_code}")
        check("el cambio quedo guardado", "Estudio de Beto (corregido)"
              in c.get("/repositorio").get_data(as_text=True))

        # --- mismo DNI escrito con puntos = mismo usuario ---
        print("\nEl DNI se normaliza:")
        c.get("/logout")
        c.post("/login", data={"nombre": "Beto Lopez", "dni": "27.999.888"})
        html = c.get("/repositorio").get_data(as_text=True)
        check("con puntos entra como el mismo usuario y edita lo suyo",
              "btn-editar" in html)

        # --- borrar: solo admin ---
        print("\nBorrar (solo admin):")
        r = c.post(f"/estudios/{id_beto}/borrar")
        check("un usuario comun no puede borrar", r.status_code == 403,
              f"status {r.status_code}")

        # --- ya no queda nada de OAFCare ---
        print("\nOAFCare eliminado:")
        for ruta in ["/pacientes", "/pacientes/nuevo", "/buscar", "/inactividad",
                     "/pacientes_alta", "/estadisticas", "/dashboard"]:
            r = c.get(ruta)
            check(f"GET {ruta} ya no existe (404)", r.status_code == 404,
                  f"status {r.status_code}")

        html = c.get("/").get_data(as_text=True)
        for texto in ["Pacientes", "Dashboard", "Inactividad", "Exportar CSV"]:
            check(f"el nav ya no tiene '{texto}'", texto not in html)

        # --- la base tiene UNA sola tabla ---
        print("\nEsquema:")
        import sqlite3 as _sq
        _c = _sq.connect(db_path)
        tablas = sorted(
            r[0] for r in _c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
        )
        _c.close()
        check("solo queda la tabla estudios", tablas == ["estudios"], str(tablas))

        # --- acentos: ninguna pantalla con la codificacion rota ---
        # "Ã", "Â" y "â€" son lo que se ve cuando bytes UTF-8 se guardaron
        # leidos como Latin-1. Ya paso con inicio.html.
        print("\nCodificacion (acentos):")
        for ruta in ["/login", "/", "/nueva-investigacion", "/repositorio",
                     "/modificar", "/como-comenzar"]:
            texto = c.get(ruta).get_data(as_text=True)
            rotos = {m: texto.count(m) for m in ("Ã", "Â", "â€") if m in texto}
            check(f"{ruta} sin caracteres rotos", not rotos, str(rotos))

except Exception:
    print("\nEXCEPCION:")
    traceback.print_exc()
    fallos.append("excepcion no manejada")

finally:
    try:
        os.remove(db_path)
    except OSError:
        pass

print("\n" + "=" * 60)
if fallos:
    print(f"RESULTADO: {len(fallos)} FALLA(S)")
    for f in fallos:
        print(f"  - {f}")
else:
    print("RESULTADO: TODO OK")
print("=" * 60)

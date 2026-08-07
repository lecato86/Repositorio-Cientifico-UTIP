# Repositorio Científico UTIP — Guía para agentes IA

Aplicación web Flask para el repositorio científico de la UTIP (Unidad de Terapia Intensiva Pediátrica). Registra investigaciones: se cargan por un formulario dividido en apartados, se consultan en una tabla completa y solo las modifica quien las cargó.

**El paquete Python se llama `oafcare`** por herencia: el proyecto derivaba de OAFCare (seguimiento de pacientes en kinesiología respiratoria). Ese dominio se eliminó por completo — no quedan pacientes, atenciones, gráficos ni sus tablas. No renombrar el paquete.

## Cómo correr el proyecto

```bash
# Desarrollo (hot reload)
python run_dev.py

# Producción
python app.py
```

La base de datos (`pacientes.db` en SQLite local, nombre también heredado) se crea automáticamente al iniciar si no existe.

## Arquitectura

```
app.py                  # Entry point (4 líneas)
config.py               # Config desde .env
oafcare/
  __init__.py           # create_app() — registra blueprints, login_manager, globals
  database.py           # get_db(), init_db(), migraciones de `estudios`
  auth/                 # Blueprint: /login, /logout. Sin contraseña ni tabla
  estudios/             # Blueprint ÚNICO: el repositorio de investigaciones
    models.py           # SQL de la tabla `estudios` + puede_modificar()
    routes.py           # /, /nueva-investigacion, /repositorio, /modificar, /como-comenzar
  utils/
    estudio.py          # Formulario: opciones, ESTUDIO_COLUMNAS, parsers
    repositorio.py      # Columnas y agrupación de la vista "Consultar repositorio"
    docs.py             # Lista los PDFs de static/docs/ para "Cómo comenzar"
scripts/
  backup_db.py          # Backup/restore de `estudios` a JSON + CSV (backups/, gitignoreado)
  smoke_test.py         # Prueba de humo end-to-end (descartable, no es del proyecto)
templates/
  base.html             # Layout + navbar
  auth/login.html       # Ingreso: nombre y apellido + DNI
  estudios/             # inicio, nueva, _apartados, repositorio, modificar,
                        # como_comenzar, no_autorizado
static/
  css/                  # base.css, login.css, inicio.css, estudio.css, repositorio.css
  js/                   # ingreso_wizard.js, estudio_form.js, repositorio.js
  docs/                 # PDFs de "Cómo comenzar" (se listan solos, ver utils/docs.py)
```

**Un solo dominio, una sola tabla.** Todo lo que se agregue va en `estudios/` y `utils/estudio.py`.

## Reglas importantes

### Gestión de entorno y configuración
- **Las credenciales y valores sensibles van en `.env`** (SECRET_KEY, DATABASE_URL, ADMIN_DNIS). **Nunca se commitean** y nunca se hardcodean en el código.
- `.env` está en `.gitignore`. **No lo subas al repo jamás.**
- **`.env.example` es la plantilla** y **sí se commitea**. Mantenelo actualizado: cada variable nueva de `Config` va también ahí (con comentario y sin valor real).
- **Toda la configuración se centraliza en la clase `Config` de `config.py`**, que es la ÚNICA que lee `os.environ`. Se carga con `app.config.from_object(Config)` en `create_app()`.
- **El resto del código accede a la config con `current_app.config["NOMBRE"]`**, **nunca con `os.getenv()`/`os.environ` directo.**
- `Config.validate()` corre en `create_app()` y aborta con un mensaje claro si falta una variable obligatoria: `SECRET_KEY` siempre; `DATABASE_URL` cuando `DEBUG=False` (producción).

### Base de datos
- **La app tiene UNA sola tabla: `estudios`.** No agregar tablas sin necesidad real; los campos de una investigación son columnas de `estudios`.
- **Nunca modificar la DB directamente.** Toda modificación al esquema va en `oafcare/database.py`.
- **Soporta dos motores:** Postgres si hay `DATABASE_URL` (producción, ej. Neon en Render), SQLite si no (desarrollo local). El esquema se crea en `_init_postgres()` / `_init_sqlite()`.
- `_borrar_tablas_oafcare()` corre en cada arranque y hace `DROP TABLE IF EXISTS` de las tablas heredadas (`pacientes`, `atenciones_diarias`, `mediciones_oaf`, `historial`, `deduplicacion_pacientes`, `usuarios`). Es idempotente y alcanza a la base de producción sin intervención manual. Se puede quitar cuando no queden bases viejas.
- `init_db()` usa una conexión directa (no `get_db()`) porque se llama fuera del contexto de request.
- **Persistencia:** en Render el disco es efímero — SQLite ahí pierde todo en cada deploy. Por eso `Config.validate()` exige `DATABASE_URL` siempre que detecta Render (variable `RENDER`, la setea Render solo), sin importar `DEBUG`. No relajar ese guard.
- **Backups:** `python scripts/backup_db.py` genera en `backups/` un dump `utip_backup_<stamp>.json` (para restaurar) **y** `utip_backup_<stamp>_csv/estudios.csv` (para Excel, utf-8-sig). `--restore <archivo.json>` restaura (con `--force` pisa lo existente; el JSON es la fuente de verdad, el CSV es solo para lectura humana). Usa `BACKUP_DATABASE_URL` si está seteada (la base de producción en Neon), si no `DATABASE_URL`, si no la SQLite local. Contienen las investigaciones y el DNI de quien las cargó: **nunca commitearlos** (`backups/` está en `.gitignore`).

### Autenticación — ingreso sin contraseña (nombre y apellido + DNI)
- **No hay passwords ni tabla de usuarios.** En `/login` se completan dos campos: **nombre y apellido** y **DNI**. Con eso se entra.
- La identidad **vive en la cookie de sesión** (firmada con `SECRET_KEY`): `Usuario.get_id()` devuelve `"<dni>|<nombre>"` y el `user_loader` la reconstruye en cada request. No hay nada que persistir.
- **El DNI es la identidad**, no el nombre: los nombres se repiten y se escriben distinto. `normalizar_dni()` deja solo los dígitos, así `30.123.456` y `30123456` son la misma persona. El nombre es solo para mostrar.
- **Roles:** todo el que entra es `editor` (puede cargar y editar lo suyo). Es `admin` si su DNI está en `ADMIN_DNIS` del `.env`; lo único que suma es **borrar** registros. `Usuario.rol` es una property que lee la config en cada request, así que cambiar `ADMIN_DNIS` tiene efecto al reiniciar, sin tocar nada más.
- Las rutas de escritura llevan `requiere_editor` / `requiere_admin` de `oafcare/auth/decorators.py`.

### Propiedad de las investigaciones
- **Consultar puede cualquiera; modificar, solo quien la cargó.** `crear_estudio` guarda `creado_por` (nombre, para mostrar) y `creado_por_dni` (la identidad).
- `puede_modificar(estudio, usuario)` en `estudios/models.py` compara los DNIs. Una investigación sin `creado_por_dni` no tiene dueño y no se puede editar.
- El chequeo va en **las dos** rutas, `editar` (GET) y `actualizar` (POST): el POST es una URL más y puede llegar sin pasar por el formulario. Si falla, se devuelve `estudios/no_autorizado.html` con **403** y el cartel `MSG_NO_ES_TU_ESTUDIO`.
- En la UI las ajenas no ofrecen la acción: `repositorio.html` y `modificar.html` reciben un dict `editables` (`{id: bool}`) armado en la ruta. Si agregás otra vista con acción de editar, pasale lo mismo.

### Rutas y url_for
- Siempre usar el namespace del blueprint: `url_for('estudios.inicio')`, `url_for('auth.login')`.
- `login_manager.login_view` está seteado a `"auth.login"`. Después del login se va a `estudios.inicio`.

### Pantalla de inicio (estudios/inicio.html)
- `/` (`estudios.inicio`) es un **menú de cuatro opciones**. Cada opción es una tarjeta de `.inicio-grid` (estilos en `static/css/inicio.css`):
  1. **Cargar nueva investigación** → `estudios.nueva` (`/nueva-investigacion`): el formulario por apartados, POST a `estudios.guardar` (misma URL).
  2. **Consultar repositorio** → `estudios.repositorio` (`/repositorio`): la base completa en una tabla.
  3. **Modificar investigación cargada** → `estudios.modificar` (`/modificar`): búsqueda por título.
  4. **Cómo comenzar** → `estudios.como_comenzar` (`/como-comenzar`): guía + PDFs.
- Las opciones 1 y 3 escriben en la base: llevan `@requiere_editor` y en el menú se muestran deshabilitadas (`.opcion.is-bloqueada`) para quien no pueda editar, en vez de ocultarse. Si agregás una opción que escribe, replicá las dos cosas (decorador **y** estado bloqueado).

### Formulario de investigaciones (estudios/_apartados.html)
- **El formulario está dividido en apartados**, uno por paso: un solo `<form>`, cada apartado es un `<section class="wizard-step">` y la navegación la maneja `static/js/ingreso_wizard.js` (que toma la cantidad de pasos del DOM — no hay que tocarlo al sumar apartados). Estilos en `static/css/estudio.css`, que es autocontenido (la tarjeta, el stepper y la barra de navegación salían de `patients.css`, eliminado con el resto de OAFCare).
- **Un solo template para "cargar" y "modificar"**: `estudios/nueva.html` incluye `_apartados.html` y recibe `form_action` + `e` (dict con lo guardado, `{}` si es nueva). `estudios.nueva` lo usa vacío, `estudios.editar` prellenado.
- Apartados actuales: **1) Sobre el estudio** — título (obligatorio), tema, origen de los datos, temporalidad.
- **Para agregar una pregunta**, en este orden: definí sus opciones en `utils/estudio.py` → agregá su columna a `ESTUDIO_COLUMNAS` (el `CREATE TABLE` y la migración salen de esa lista, no se toca SQL) → leela en `estudio_desde_form` → mostrala en `_apartados.html` → si va en la vista de repositorio, agregala a `GRUPOS_REPOSITORIO`.
- **Para agregar un apartado**: otro `<section class="wizard-step">` y su `<li>` en el `.stepper`.
- `fuente_datos` guarda **el texto completo de la opción**, no un código. La opción "De otras fuentes (especificar)" (constante `FUENTE_DATOS_OTRA`) habilita el textarea `fuente_datos_otra`, que `static/js/estudio_form.js` muestra u oculta según el select. **El detalle solo se persiste si esa opción quedó elegida** (lo filtra `fuente_datos_desde_form`), así no queda texto colgado si el usuario cambia de opción. Sin JS el campo queda visible: es el comportamiento seguro.
- Las opciones se inyectan a las plantillas desde `inject_globals()` (`FUENTES_DATOS`, `FUENTE_DATOS_OTRA`, `TEMPORALIDADES`).

### Tabla `estudios`
- Una fila por investigación, PK `id` autoincremental (`SERIAL` en Postgres, `INTEGER ... AUTOINCREMENT` en SQLite). Todas las columnas del formulario son TEXT.
- **Las columnas se generan desde `ESTUDIO_COLUMNAS`** (en `utils/estudio.py`): `_estudios_columnas_sql()` arma el `CREATE TABLE` en los dos motores y las migraciones agregan las que falten (`ADD COLUMN IF NOT EXISTS` en Postgres, `_add_column_if_missing` en SQLite). Agregar un campo es una línea en esa lista.
- Además, las columnas de `ESTUDIO_COLUMNAS_META` (en `database.py`, también migradas en los dos motores): `creado_por` (nombre del autor), `creado_por_dni` (su DNI — el que decide quién puede editar), `creado_en`, `actualizado_en`.
- `crear_estudio` **no devuelve el id**: obtenerlo difiere entre SQLite (`lastrowid`) y Postgres (`RETURNING`), y ningún flujo lo necesita porque después de guardar se va al repositorio. No agregar esa dependencia sin resolver los dos motores.
- `actualizar_estudio` escribe **todas** las columnas del formulario (sin `COALESCE`): el form manda siempre el conjunto completo y un campo borrado a propósito tiene que quedar vacío.

### Consultar repositorio (estudios/repositorio.html)
- Vista completa de la tabla `estudios`: una fila por investigación, todas las columnas, la más reciente primero.
- **Qué columnas se muestran y cómo se agrupan está en `utils/repositorio.py`**, en `GRUPOS_REPOSITORIO` (lista de `(título del grupo, [(clave, etiqueta), ...])`). El encabezado tiene dos filas: los apartados y las preguntas. Al sumar un campo, agregalo también acá o no aparece.
- Las claves tienen que existir en la fila: una clave inexistente hace fallar el template (`sqlite3.Row` levanta `IndexError`). `COLUMNAS_FIJAS` quedan pegadas a la izquierda al scrollear (`position: sticky`, desactivado por media query en pantallas angostas); `COLUMNAS_LARGAS` son las que parten en varias líneas en vez de estirar la tabla.
- El filtro de la barra superior es **cliente** (`static/js/repositorio.js`): filtra las filas ya renderizadas por texto, no vuelve al servidor. Cachea el texto de cada fila una sola vez.
- `guardar` y `actualizar` redirigen acá al terminar, para que se vea el registro recién cargado.

### Modificar investigación cargada (estudios/modificar.html)
- Se identifica el registro **solo por título** (`buscar_estudios_por_titulo`, `LOWER(...) LIKE` para que funcione igual en SQLite y Postgres).
- La búsqueda lista **todas** las coincidencias, sean de quien sean. Redirige directo a `estudios.editar` solo cuando hay **una sola coincidencia Y es del usuario en sesión**; las ajenas se listan sin link, con la clase `.inv-ajena`. Los títulos no son únicos: dos investigaciones pueden compartirlo.

### Cómo comenzar (estudios/como_comenzar.html)
- Guía de arranque + PDFs descargables. **Los PDFs no están hardcodeados**: `utils/docs.py` lista los `.pdf` de `static/docs/` y arma el título desde el nombre del archivo. Para publicar material nuevo se copia el archivo ahí, sin tocar código. Si la carpeta no existe, la lista queda vacía sin fallar.

### CSS
- `base.css` tiene reglas globales: `input, select { width: 100% }`. Para overridear en un contexto específico, usar `width: auto` inline o en el CSS del módulo.
- Para agregar estilos específicos a una página usar el bloque `{% block extra_css %}`.

### Templates
- Todos extienden `base.html`, salvo `auth/login.html`, que es una página suelta (no muestra el navbar).
- El navbar está en `base.html`. Si necesita verse diferente en una página, hacerlo con CSS en el stylesheet de esa página, no duplicando el HTML.

## Hosting
El proyecto **no puede correr en Netlify ni en ningún hosting estático**: es una app Flask y necesita un proceso Python. Render, Railway, Fly.io o PythonAnywhere sirven. En cualquiera hay que setear `SECRET_KEY` y `DATABASE_URL` en el panel, o `Config.validate()` aborta el arranque.

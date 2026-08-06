# Repositorio Científico UTIP — Guía para agentes IA

Aplicación web Flask para el repositorio científico de la UTIP (Unidad de Terapia Intensiva Pediátrica). Deriva de OAFCare (seguimiento de pacientes en kinesiología respiratoria) y conserva su base: registra investigaciones de casos con OAF, atenciones diarias, soporte ventilatorio, evolución clínica y gráficos estadísticos.

**El paquete Python sigue llamándose `oafcare`** y en la base de datos una "investigación" es una fila de la tabla `pacientes`. El vocabulario de la interfaz habla de investigaciones; el del código, de pacientes. No renombrar el paquete ni las tablas.

## Cómo correr el proyecto

```bash
# Desarrollo (hot reload)
python run_dev.py

# Producción
python app.py
```

La base de datos (`pacientes.db`) se crea automáticamente al iniciar la app si no existe.

## Arquitectura

```
app.py                  # Entry point (4 líneas)
config.py               # Config desde .env
oafcare/
  __init__.py           # create_app() — registra blueprints, login_manager, filtros
  database.py           # get_db(), init_db(), migraciones, seed de usuarios
  auth/                 # Blueprint: /login, /logout
  estudios/             # Blueprint PRINCIPAL: repositorio de investigaciones
    models.py           # SQL de la tabla `estudios` (armado desde ESTUDIO_COLUMNAS)
    routes.py           # /, /nueva-investigacion, /repositorio, /modificar, /como-comenzar
  patients/             # Blueprint HEREDADO (OAF): pacientes, atenciones, altas
    models.py           # Funciones SQL (get_paciente, guardar_atencion, etc.)
    services.py         # Lógica de negocio (trayectoria_ventilatoria_data)
    routes.py           # Rutas HTTP
  charts/               # Blueprint: dashboard, estadísticas, evolución, gráficos (OAF)
    matplotlib_charts.py  # Genera PNGs con matplotlib
    routes.py
  utils/
    estudio.py          # Formulario de investigaciones: opciones, ESTUDIO_COLUMNAS, parsers
    repositorio.py      # Columnas y agrupación de la vista "Consultar repositorio"
    docs.py             # Lista los PDFs de static/docs/ para "Cómo comenzar"
    edad.py             # parse_edad_meses, formato_edad (OAF)
    soporte.py          # SALAS, SOPORTES, soporte_desde_form, soporte_en_fecha (OAF)
    muestras.py         # MUESTRAS, muestras_desde_form (OAF)
    ingreso.py          # Formulario de ingreso OAF: SEXOS, SALAS_DERIVACION,
                        # ESTADOS_VIRUS, VIRUS_PANEL + parsers
scripts/
  backup_db.py          # Backup/restore de la DB a JSON (backups/, gitignoreado)
templates/
  estudios/             # Repositorio: inicio, nueva, repositorio, modificar, como_comenzar
  patients/, charts/    # OAF (heredado)
static/
  css/                  # base.css, inicio.css, estudio.css, repositorio.css, patients.css, dashboard.css
  js/                   # ingreso_wizard.js, estudio_form.js, repositorio.js, date_picker.js, trajectory.js
  docs/                 # PDFs de "Cómo comenzar" (se listan solos, ver utils/docs.py)
```

### Dos dominios en una misma app
- **`estudios` es el dominio principal**: las investigaciones del repositorio, tabla `estudios`. Sirve `/` y las cuatro opciones del menú de inicio.
- **`patients` + `charts` son OAFCare heredado**: seguimiento de pacientes en OAF, tablas `pacientes` / `atenciones_diarias` / `mediciones_oaf` / `historial`. Sigue funcionando y accesible desde el nav (después del separador `.nav-sep`), pero **está fuera del flujo del repositorio**. No mezclar los dos dominios: una investigación NO es un paciente.
- Trabajo nuevo sobre el repositorio va en `estudios/` y `utils/estudio.py`. No agregar campos de investigación a la tabla `pacientes`.

## Reglas importantes

### Gestión de entorno y configuración
- **Las credenciales y valores sensibles van en `.env`** (SECRET_KEY, DATABASE_URL, SEED_USERS, etc.). **Nunca se commitean** y nunca se hardcodean en el código.
- `.env` está en `.gitignore`. **No lo subas al repo jamás.**
- **`.env.example` es la plantilla** y **sí se commitea**. Mantenelo actualizado: cada vez que agregues una variable nueva a `Config`, agregala también a `.env.example` (con comentario y sin valor real).
- **Toda la configuración se centraliza en la clase `Config` de `config.py`**, que es la ÚNICA que lee `os.environ`. Se carga con `app.config.from_object(Config)` en `create_app()`.
- **El resto del código accede a la config con `current_app.config["NOMBRE"]`** (o `app.config[...]`), **nunca con `os.getenv()`/`os.environ` directo.**
- `Config.validate()` corre en `create_app()` y aborta con un mensaje claro si falta una variable obligatoria: `SECRET_KEY` siempre; `DATABASE_URL` cuando `DEBUG=False` (producción).

### Base de datos
- **Nunca modificar la DB directamente.** Toda modificación al esquema va en `oafcare/database.py`.
- **Soporta dos motores:** Postgres si hay `DATABASE_URL` (producción, ej. Neon en Render), SQLite si no (desarrollo local). El esquema se crea en `_init_postgres()` / `_init_sqlite()`.
- Las migraciones SQLite legacy se aplican en `_init_sqlite()` → `_migrate_edad_to_integer()`, etc. (solo aplican a bases SQLite viejas).
- **Tabla `mediciones_oaf`:** guarda la tabla de monitoreo del ingreso (una fila por tiempo: `hc, orden, tiempo, fc, fr, sato2, score_tal, fio2, flujo`, todo TEXT salvo `orden`). Es datos de serie temporal, por eso va en tabla propia y NO como columnas de `pacientes`. Se crea en ambos `CREATE TABLE`. Se escribe con `guardar_mediciones_oaf(hc, filas)` (borra y reinserta; ignora filas sin ningún valor y no toca lo existente si no vino ninguna con datos).
- **Columnas del ingreso:** los campos del formulario de ingreso viven en la tabla `pacientes` y se listan una sola vez en `PACIENTE_COLUMNAS_INGRESO` (en `database.py`, mantener sincronizado con `utils/ingreso.py`). Se crean en ambos `CREATE TABLE` y se agregan a bases existentes por migración: `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` en Postgres y `_add_column_if_missing()` en SQLite. Ese `_add_column_if_missing` en SQLite va **después** de `_migrate_edad_to_integer()`, que recrea la tabla en bases legacy y borraría las columnas nuevas si se agregaran antes. Para sumar un campo de ingreso nuevo: agregalo a `PACIENTE_COLUMNAS_INGRESO`, a los dos `CREATE TABLE`, a `upsert_paciente` y a `utils/ingreso.py`.
- El seed de usuarios está en `_seed_usuarios()`: crea los usuarios de `Config.SEED_USUARIOS` (leídos de `SEED_USERS`) solo si la tabla `usuarios` está vacía.
- `init_db()` usa una conexión directa (no `get_db()`) porque se llama fuera del contexto de request.
- **Persistencia:** en Render el disco es efímero — SQLite ahí pierde todo en cada deploy. Por eso `Config.validate()` exige `DATABASE_URL` siempre que detecta Render (variable `RENDER`, la setea Render solo), sin importar `DEBUG`. No relajar ese guard.
- **Backups:** `python scripts/backup_db.py` genera en `backups/` un dump completo `oafcare_backup_<stamp>.json` (para restaurar) **y** una carpeta `oafcare_backup_<stamp>_csv/` con una planilla CSV por tabla (para abrir en Excel, utf-8-sig). `--restore <archivo.json>` restaura (con `--force` pisa datos existentes; el JSON es la fuente de verdad para restore, el CSV es solo para lectura humana). El script usa `BACKUP_DATABASE_URL` si está seteada (la base de producción en Neon), si no `DATABASE_URL`, si no la SQLite local. Los backups contienen datos de pacientes y `backups/` está en `.gitignore`: **nunca commitearlos**.

### Autenticación
- Las contraseñas se hashean con `werkzeug.security.generate_password_hash`. Nunca guardar passwords en texto plano.
- Los roles son `admin`, `editor`, `lector`. Las rutas de escritura requieren `requiere_editor` de `oafcare/auth/decorators.py`.

### Rutas y url_for
- Siempre usar el namespace del blueprint: `url_for('estudios.inicio')`, `url_for('auth.login')`, `url_for('patients.listar_pacientes')`, `url_for('charts.dashboard')`.
- `login_manager.login_view` está seteado a `"auth.login"`. Después del login se va a `estudios.inicio`.

### Pantalla de inicio (estudios/inicio.html)
- `/` (`estudios.inicio`) es un **menú de cuatro opciones**. Cada opción es una tarjeta de `.inicio-grid` (estilos en `static/css/inicio.css`):
  1. **Cargar nueva investigación** → `estudios.nueva` (`/nueva-investigacion`): el formulario por apartados, POST a `estudios.guardar` (misma URL).
  2. **Consultar repositorio** → `estudios.repositorio` (`/repositorio`): la base completa en una tabla.
  3. **Modificar investigación cargada** → `estudios.modificar` (`/modificar`): búsqueda por título.
  4. **Cómo comenzar** → `estudios.como_comenzar` (`/como-comenzar`): guía + PDFs.
- Las opciones 1 y 3 escriben en la base: llevan `@requiere_editor` y en el menú se muestran deshabilitadas (`.opcion.is-bloqueada`) para el rol `lector`, en vez de ocultarse. Si agregás una opción que escribe, replicá las dos cosas (decorador **y** estado bloqueado).

### Formulario de investigaciones (estudios/_apartados.html)
- **El formulario está dividido en apartados**, uno por paso, con la misma mecánica que el wizard OAF: un solo `<form>`, cada apartado es un `<section class="wizard-step">` y la navegación la maneja `static/js/ingreso_wizard.js` (que toma la cantidad de pasos del DOM — no hay que tocarlo al sumar apartados). Estilos propios en `static/css/estudio.css`; los del contenedor salen de `patients.css` (`.card.ingreso`, `.stepper`, `.wizard-nav`).
- **Un solo template para "cargar" y "modificar"**: `estudios/nueva.html` incluye `_apartados.html` y recibe `form_action` + `e` (dict con lo guardado, `{}` si es nueva). `estudios.nueva` lo usa vacío, `estudios.editar` prellenado.
- Apartados actuales: **1) Sobre el estudio** — título (obligatorio), tema, origen de los datos, temporalidad.
- **Para agregar una pregunta**, en este orden: definí sus opciones en `utils/estudio.py` → agregá su columna a `ESTUDIO_COLUMNAS` (el `CREATE TABLE` y la migración salen de esa lista, no se toca SQL) → leela en `estudio_desde_form` → mostrala en `_apartados.html` → si va en la vista de repositorio, agregala a `GRUPOS_REPOSITORIO`.
- **Para agregar un apartado**: otro `<section class="wizard-step">` y su `<li>` en el `.stepper`.
- `fuente_datos` guarda **el texto completo de la opción**, no un código. La opción "De otras fuentes (especificar)" (constante `FUENTE_DATOS_OTRA`) habilita el textarea `fuente_datos_otra`, que `static/js/estudio_form.js` muestra u oculta según el select. **El detalle solo se persiste si esa opción quedó elegida** (lo filtra `fuente_datos_desde_form`), así no queda texto colgado si el usuario cambia de opción. Sin JS el campo queda visible: es el comportamiento seguro.
- Las opciones se inyectan a las plantillas desde `inject_globals()` (`FUENTES_DATOS`, `FUENTE_DATOS_OTRA`, `TEMPORALIDADES`).

### Tabla `estudios`
- Una fila por investigación, PK `id` autoincremental (`SERIAL` en Postgres, `INTEGER ... AUTOINCREMENT` en SQLite). Todas las columnas del formulario son TEXT.
- **Las columnas se generan desde `ESTUDIO_COLUMNAS`** (en `utils/estudio.py`): `_estudios_columnas_sql()` arma el `CREATE TABLE` en los dos motores y las migraciones agregan las que falten (`ADD COLUMN IF NOT EXISTS` en Postgres, `_add_column_if_missing` en SQLite). Agregar un campo es una línea en esa lista.
- Además: `creado_por` (username), `creado_en`, `actualizado_en`.
- `crear_estudio` **no devuelve el id**: obtenerlo difiere entre SQLite (`lastrowid`) y Postgres (`RETURNING`), y ningún flujo lo necesita porque después de guardar se va al repositorio. No agregar esa dependencia sin resolver los dos motores.
- `actualizar_estudio` escribe **todas** las columnas del formulario (sin `COALESCE`): el form manda siempre el conjunto completo y un campo borrado a propósito tiene que quedar vacío. Esto es distinto de `upsert_paciente` (OAF), que sí preserva con `COALESCE`.

### Consultar repositorio (estudios/repositorio.html)
- Vista completa de la tabla `estudios`: una fila por investigación, todas las columnas, la más reciente primero.
- **Qué columnas se muestran y cómo se agrupan está en `utils/repositorio.py`**, en `GRUPOS_REPOSITORIO` (lista de `(título del grupo, [(clave, etiqueta), ...])`). El encabezado tiene dos filas: los apartados y las preguntas. Al sumar un campo, agregalo también acá o no aparece.
- Las claves tienen que existir en la fila: una clave inexistente hace fallar el template (`sqlite3.Row` levanta `IndexError`). `COLUMNAS_FIJAS` quedan pegadas a la izquierda al scrollear (`position: sticky`, desactivado por media query en pantallas angostas); `COLUMNAS_LARGAS` son las que parten en varias líneas en vez de estirar la tabla.
- El filtro de la barra superior es **cliente** (`static/js/repositorio.js`): filtra las filas ya renderizadas por texto, no vuelve al servidor. Cachea el texto de cada fila una sola vez.
- `guardar` y `actualizar` redirigen acá al terminar, para que se vea el registro recién cargado.

### Modificar investigación cargada (estudios/modificar.html)
- Se identifica el registro **solo por título** (`buscar_estudios_por_titulo`, `LOWER(...) LIKE` para que funcione igual en SQLite y Postgres).
- Con **una sola coincidencia** redirige directo a `estudios.editar`; con varias muestra la lista para elegir. Los títulos no son únicos: dos investigaciones pueden compartirlo.

### Cómo comenzar (estudios/como_comenzar.html)
- Guía de arranque + PDFs descargables. **Los PDFs no están hardcodeados**: `utils/docs.py` lista los `.pdf` de `static/docs/` y arma el título desde el nombre del archivo. Para publicar material nuevo se copia el archivo ahí, sin tocar código. Si la carpeta no existe, la lista queda vacía sin fallar.

### CSS
- `base.css` tiene reglas globales: `input, select { width: 100% }`. Para overridear en un contexto específico, usar `width: auto` inline o en el CSS del módulo.
- El dashboard tiene tema oscuro en `dashboard.css`, que también oculta el overlay de blur con `.overlay { display: none }`.
- Para agregar estilos específicos a una página usar el bloque `{% block extra_css %}`.

### Templates
- Todos extienden `base.html`. Los macros de formulario están en `templates/macros/forms.html`.
- El navbar está en `base.html`. Si necesita verse diferente en una página (ej: dashboard oscuro), hacerlo con CSS en el stylesheet de esa página, no duplicando el HTML.

### soporte_en_fecha
- Recibe una lista de dicts `{"fecha": str, "valor_nuevo": str}` ordenada cronológicamente. Devuelve el soporte vigente en una fecha dada. No espera tuplas.

### Formulario de ingreso OAF (patients/nuevo.html) — HEREDADO
> Todo lo que sigue es del dominio OAF (pacientes), no del repositorio de investigaciones. Se conserva funcionando; el formulario de investigaciones es otro (ver "Formulario de investigaciones" arriba).

- Es el formulario de alta/ingreso de paciente OAF (`patients.nuevo_paciente`, en `/pacientes/nuevo` → POST `patients.guardar`). No está en el nav: se entra desde el botón "Nuevo paciente" del listado. Las etiquetas de los campos de texto van como `placeholder`.
- **Es un wizard apaisado de 6 pasos** para no scrollear verticalmente: 1) Datos (nombre, HC, sexo, peso, edad, sala de derivación, Dx.), 2) Inicio OAF (fecha+hora de inicio, fecha de inicio de alimentación, soporte previo, lugar de inicio), 3) Virus, 4) Comorbilidades y complicaciones, 5) Monitoreo (tabla), 6) Resultados (fecha+hora de fin, resultado). Un solo `<form>` con `<section class="wizard-step">` y navegación por `static/js/ingreso_wizard.js` (Anterior/Siguiente, submit solo en el último paso). El form lleva `novalidate` y el JS valida los `[required]` del paso actual con `reportValidity()` antes de avanzar; Enter en inputs (no textarea) avanza en vez de mandar. El JS y el contador toman la cantidad de pasos del DOM. Estilos del wizard en `patients.css` (`.card.ingreso`, `.stepper`, `.ingreso-grid`, `.wizard-nav`, `.med-table`). Para sumar un paso: agregá otro `.wizard-step` y su `<li>` en el `.stepper`.
- Las opciones fijas y los parsers están en `utils/ingreso.py` y se inyectan a las plantillas vía `inject_globals()` (`SEXOS`, `SALAS_DERIVACION`, `ESTADOS_VIRUS`, `VIRUS_PANEL`, `COMORBILIDADES`, `SOPORTES_PREVIOS`, `LUGARES_INICIO`, `COMPLICACIONES`, `RESULTADOS_OAF`, `TIEMPOS_MEDICION`, `PARAMETROS_MEDICION`). Macros en `templates/macros/forms.html`: `sexo_select`, `sala_derivacion_radios`, `virus_panel`, `comorbilidad_checkboxes`, `edad_selects(..., max_anios=14)`, los genéricos `radio_group(name, opciones, sel)` / `checkbox_group(name, opciones, sels)`, y `mediciones_tabla`.
- **Selección única (`type="radio"`):** sala de derivación, cada virus, soporte previo, lugar de inicio y resultado. **Selección MÚLTIPLE (`checkbox`):** comorbilidades y complicaciones (se guardan en una columna de texto unidas por ", ", parseadas con `*_desde_form` / `*_seleccionadas`, que conservan el orden de la constante). El panel de virus tiene 8 virus con radios + área "Otro / Detalle" de texto libre.
- **Tabla de monitoreo** (paso 5): 6 parámetros (`PARAMETROS_MEDICION`) × 9 tiempos (`TIEMPOS_MEDICION`). Cada celda es `name="med_<paramkey>_<tiempokey>"`. Se leen con `mediciones_desde_form` y se guardan en la tabla `mediciones_oaf` (ver sección Base de datos), NO en `pacientes`.
- **Un solo formulario para "nuevo" y "editar":** el wizard vive en el include `templates/patients/_ingreso_wizard.html`. `nuevo.html` lo incluye vacío (POST a `patients.guardar`) y `edit.html` lo incluye prefilled (POST a `patients.actualizar_ultima`, con `hc_readonly=True`). El prefill se arma en `editar_ultima` con `virus_seleccionados`, `comorbilidades_seleccionadas`, `complicaciones_seleccionadas`, `mediciones_valores` y `edad_partes`. Los macros aceptan el valor seleccionado para repoblar.
- **`upsert_paciente(..., ingreso=None)`**: `ingreso` es un dict con claves = columnas de `PACIENTE_COLUMNAS_INGRESO`. En el UPDATE las columnas de ingreso usan `COALESCE(excluded.x, pacientes.x)`: si el dict no las trae se conservan. El SQL se arma dinámicamente desde las listas de columnas, así que sumar un campo de ingreso no requiere tocar el INSERT.
- **Campos legacy (soporte/sala/muestra/tq):** el form de ingreso ya NO los captura. Tanto `guardar` como `actualizar_ultima` los preservan pasando el valor actual del paciente (`_legacy_preservados`), para no pisarlos al editar. Son columnas core (se sobrescriben), por eso hay que pasarles el valor existente.
- **Misma HC = actualiza, no duplica** (upsert por PK `hc`) y **loguea los cambios** en `historial`: `_log_cambios(hc, paciente, nuevos, fecha)` compara el paciente existente contra los valores nuevos (nombre, edad, dx + todas las columnas de ingreso) y registra una fila por campo cambiado. La tabla de monitoreo se reemplaza entera (no se loguea campo por campo).
- **Estadísticas** (`charts.estadisticas`): tabla Fecha / Pacientes en OAF / Atenciones agrupada por fecha de `atenciones_diarias` (`COUNT(DISTINCT hc)` = pacientes cargados ese día), ordenada por fecha desc.
- Provisional: `guardar` inserta 1 atención por ingreso (fecha = `fecha_inicio_oaf` o hoy) porque el formulario todavía no tiene el conteo diario de atenciones. Ese flujo diario es parte de los parámetros que faltan agregar.

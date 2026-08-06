# OAFCare — Guía para agentes IA

OAFCare es una aplicación web Flask para el seguimiento de pacientes en kinesiología respiratoria. Registra atenciones diarias, soporte ventilatorio, evolución clínica y genera gráficos estadísticos.

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
  patients/             # Blueprint: formulario, lista, edición, alta, búsqueda
    models.py           # Funciones SQL (get_paciente, guardar_atencion, etc.)
    services.py         # Lógica de negocio (trayectoria_ventilatoria_data)
    routes.py           # Rutas HTTP
  charts/               # Blueprint: dashboard, estadísticas, evolución, gráficos
    matplotlib_charts.py  # Genera PNGs con matplotlib
    routes.py
  utils/
    edad.py             # parse_edad_meses, formato_edad
    soporte.py          # SALAS, SOPORTES, soporte_desde_form, soporte_en_fecha
    muestras.py         # MUESTRAS, muestras_desde_form
    ingreso.py          # Datos del formulario de ingreso: SEXOS, SALAS_DERIVACION,
                        # ESTADOS_VIRUS, VIRUS_PANEL + parsers (sexo/peso/virus_desde_form)
scripts/
  backup_db.py          # Backup/restore de la DB a JSON (backups/, gitignoreado)
templates/              # Jinja2; extienden base.html
static/
  css/                  # base.css, patients.css, dashboard.css
  js/                   # date_picker.js, trajectory.js, ingreso_wizard.js
```

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
- Siempre usar el namespace del blueprint: `url_for('auth.login')`, `url_for('patients.home')`, `url_for('charts.dashboard')`.
- `login_manager.login_view` está seteado a `"auth.login"`.

### CSS
- `base.css` tiene reglas globales: `input, select { width: 100% }`. Para overridear en un contexto específico, usar `width: auto` inline o en el CSS del módulo.
- El dashboard tiene tema oscuro en `dashboard.css`, que también oculta el overlay de blur con `.overlay { display: none }`.
- Para agregar estilos específicos a una página usar el bloque `{% block extra_css %}`.

### Templates
- Todos extienden `base.html`. Los macros de formulario están en `templates/macros/forms.html`.
- El navbar está en `base.html`. Si necesita verse diferente en una página (ej: dashboard oscuro), hacerlo con CSS en el stylesheet de esa página, no duplicando el HTML.

### soporte_en_fecha
- Recibe una lista de dicts `{"fecha": str, "valor_nuevo": str}` ordenada cronológicamente. Devuelve el soporte vigente en una fecha dada. No espera tuplas.

### Formulario de ingreso (patients/home.html)
- Es el formulario de alta/ingreso de paciente (`patients.home` → POST `patients.guardar`). Las etiquetas de los campos de texto van como `placeholder`.
- **Es un wizard apaisado de 6 pasos** para no scrollear verticalmente: 1) Datos (nombre, HC, sexo, peso, edad, sala de derivación, Dx.), 2) Inicio OAF (fecha+hora de inicio, fecha de inicio de alimentación, soporte previo, lugar de inicio), 3) Virus, 4) Comorbilidades y complicaciones, 5) Monitoreo (tabla), 6) Resultados (fecha+hora de fin, resultado). Un solo `<form>` con `<section class="wizard-step">` y navegación por `static/js/ingreso_wizard.js` (Anterior/Siguiente, submit solo en el último paso). El form lleva `novalidate` y el JS valida los `[required]` del paso actual con `reportValidity()` antes de avanzar; Enter en inputs (no textarea) avanza en vez de mandar. El JS y el contador toman la cantidad de pasos del DOM. Estilos del wizard en `patients.css` (`.card.ingreso`, `.stepper`, `.ingreso-grid`, `.wizard-nav`, `.med-table`). Para sumar un paso: agregá otro `.wizard-step` y su `<li>` en el `.stepper`.
- Las opciones fijas y los parsers están en `utils/ingreso.py` y se inyectan a las plantillas vía `inject_globals()` (`SEXOS`, `SALAS_DERIVACION`, `ESTADOS_VIRUS`, `VIRUS_PANEL`, `COMORBILIDADES`, `SOPORTES_PREVIOS`, `LUGARES_INICIO`, `COMPLICACIONES`, `RESULTADOS_OAF`, `TIEMPOS_MEDICION`, `PARAMETROS_MEDICION`). Macros en `templates/macros/forms.html`: `sexo_select`, `sala_derivacion_radios`, `virus_panel`, `comorbilidad_checkboxes`, `edad_selects(..., max_anios=14)`, los genéricos `radio_group(name, opciones, sel)` / `checkbox_group(name, opciones, sels)`, y `mediciones_tabla`.
- **Selección única (`type="radio"`):** sala de derivación, cada virus, soporte previo, lugar de inicio y resultado. **Selección MÚLTIPLE (`checkbox`):** comorbilidades y complicaciones (se guardan en una columna de texto unidas por ", ", parseadas con `*_desde_form` / `*_seleccionadas`, que conservan el orden de la constante). El panel de virus tiene 8 virus con radios + área "Otro / Detalle" de texto libre.
- **Tabla de monitoreo** (paso 5): 6 parámetros (`PARAMETROS_MEDICION`) × 9 tiempos (`TIEMPOS_MEDICION`). Cada celda es `name="med_<paramkey>_<tiempokey>"`. Se leen con `mediciones_desde_form` y se guardan en la tabla `mediciones_oaf` (ver sección Base de datos), NO en `pacientes`.
- **Un solo formulario para "nuevo" y "editar":** el wizard vive en el include `templates/patients/_ingreso_wizard.html`. `home.html` lo incluye vacío (POST a `patients.guardar`) y `edit.html` lo incluye prefilled (POST a `patients.actualizar_ultima`, con `hc_readonly=True`). El prefill se arma en `editar_ultima` con `virus_seleccionados`, `comorbilidades_seleccionadas`, `complicaciones_seleccionadas`, `mediciones_valores` y `edad_partes`. Los macros aceptan el valor seleccionado para repoblar.
- **`upsert_paciente(..., ingreso=None)`**: `ingreso` es un dict con claves = columnas de `PACIENTE_COLUMNAS_INGRESO`. En el UPDATE las columnas de ingreso usan `COALESCE(excluded.x, pacientes.x)`: si el dict no las trae se conservan. El SQL se arma dinámicamente desde las listas de columnas, así que sumar un campo de ingreso no requiere tocar el INSERT.
- **Campos legacy (soporte/sala/muestra/tq):** el form de ingreso ya NO los captura. Tanto `guardar` como `actualizar_ultima` los preservan pasando el valor actual del paciente (`_legacy_preservados`), para no pisarlos al editar. Son columnas core (se sobrescriben), por eso hay que pasarles el valor existente.
- **Misma HC = actualiza, no duplica** (upsert por PK `hc`) y **loguea los cambios** en `historial`: `_log_cambios(hc, paciente, nuevos, fecha)` compara el paciente existente contra los valores nuevos (nombre, edad, dx + todas las columnas de ingreso) y registra una fila por campo cambiado. La tabla de monitoreo se reemplaza entera (no se loguea campo por campo).
- **Estadísticas** (`charts.estadisticas`): tabla Fecha / Pacientes en OAF / Atenciones agrupada por fecha de `atenciones_diarias` (`COUNT(DISTINCT hc)` = pacientes cargados ese día), ordenada por fecha desc.
- Provisional: `guardar` inserta 1 atención por ingreso (fecha = `fecha_inicio_oaf` o hoy) porque el formulario todavía no tiene el conteo diario de atenciones. Ese flujo diario es parte de los parámetros que faltan agregar.

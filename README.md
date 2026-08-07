# Repositorio Científico UTIP

Aplicación web para el repositorio de investigaciones de la UTIP (Unidad de Terapia Intensiva Pediátrica). Permite cargar investigaciones por un formulario guiado, consultarlas todas en una tabla y modificarlas.

## Funcionalidades

- Ingreso sin contraseña: nombre y apellido + DNI
- Carga de investigaciones con un formulario dividido en apartados
- Consulta del repositorio completo, con filtro de texto
- Modificación de una investigación buscándola por título
- **Cada investigación solo la puede modificar quien la cargó** (se compara el DNI)
- Guía "Cómo comenzar" con documentos PDF descargables
- Backup y restore de la base a JSON y CSV

## Requisitos

- Python 3.10+
- Las dependencias están en `requirements.txt`

## Instalación

```bash
git clone <repo>
cd Repositorio-Cientifico-UTIP
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copiar `.env.example` a `.env` y completarlo. Como mínimo:

```env
SECRET_KEY=una-clave-secreta-larga-y-aleatoria
DATABASE=pacientes.db
DEBUG=True
```

Generar la clave con:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Sin `SECRET_KEY` la app no arranca (aborta con un mensaje explicando qué falta).

## Uso

**Desarrollo** (con hot reload):

```bash
python run_dev.py
```

**Producción:**

```bash
python app.py
# o con gunicorn:
gunicorn app:app
```

La base de datos se crea automáticamente al iniciar. No hay usuarios que crear: quien entra queda identificado por su DNI.

Para que alguien pueda **borrar** investigaciones, su DNI va en `ADMIN_DNIS` del `.env`, separado por comas.

## Hosting

Es una app Flask: necesita un servidor que ejecute Python. **No funciona en Netlify, GitHub Pages ni ningún hosting estático.** Sirven Render, Railway, Fly.io o PythonAnywhere. En el panel del servicio hay que setear `SECRET_KEY` y `DATABASE_URL` (Postgres); en Render `DATABASE_URL` es obligatoria porque el disco es efímero y con SQLite los datos se perderían en cada deploy.

## Backups

```bash
python scripts/backup_db.py                        # crea backups/utip_backup_<fecha>.json + CSV
python scripts/backup_db.py --restore <archivo>    # restaura (--force pisa lo existente)
```

Los backups contienen las investigaciones y el DNI de quien las cargó: `backups/` está en `.gitignore` y no se commitea.

## Estructura

```
app.py                  # Entry point
config.py               # Configuración desde .env
run_dev.py              # Servidor de desarrollo con hot reload
oafcare/                # (el paquete conserva el nombre del proyecto del que derivó)
  __init__.py           # Application factory (create_app)
  database.py           # Capa de DB: get_db, init_db, migraciones
  auth/                 # Login por nombre + DNI, sin contraseña ni tabla
  estudios/             # Rutas y SQL del repositorio de investigaciones
  utils/                # Opciones del formulario, vista de repositorio, PDFs
templates/              # Jinja2 (extienden base.html)
static/
  css/                  # base.css, login.css, inicio.css, estudio.css, repositorio.css
  js/                   # ingreso_wizard.js, estudio_form.js, repositorio.js
scripts/                # backup_db.py, smoke_test.py
```

## Stack

- [Flask](https://flask.palletsprojects.com/) — framework web
- [Flask-Login](https://flask-login.readthedocs.io/) — manejo de sesión
- [SQLite3](https://docs.python.org/3/library/sqlite3.html) / [psycopg](https://www.psycopg.org/) — SQLite en desarrollo, Postgres en producción
- [livereload](https://livereload.readthedocs.io/) — hot reload en desarrollo

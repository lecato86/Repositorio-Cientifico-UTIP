# OAFCare

Aplicación web para el seguimiento de pacientes en kinesiología respiratoria. Permite registrar atenciones diarias, soporte ventilatorio, evolución clínica y generar estadísticas y gráficos.

## Funcionalidades

- Registro de pacientes y atenciones diarias
- Seguimiento de soporte ventilatorio con trayectoria temporal
- Gráficos estadísticos: atenciones por día, distribución de soportes, diagnósticos, salas
- Dashboard con filtros por rango de fechas
- Exportación de datos a CSV (individual y global)
- Alerta de pacientes sin actividad hace 3+ días
- Buscador por nombre o número de historia clínica
- Sistema de roles: `admin`, `editor`, `lector`

## Requisitos

- Python 3.10+
- Las dependencias están en `requirements.txt`

## Instalación

```bash
git clone <repo>
cd OAFCare
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Crear el archivo `.env` en la raíz del proyecto:

```env
SECRET_KEY=una-clave-secreta-larga-y-aleatoria
DATABASE=pacientes.db
DEBUG=False
```

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

La base de datos se crea automáticamente al iniciar la app. Los usuarios por defecto se crean en el primer arranque.

## Estructura

```
app.py                  # Entry point
config.py               # Configuración desde .env
run_dev.py              # Servidor de desarrollo con hot reload
oafcare/
  __init__.py           # Application factory (create_app)
  database.py           # Capa de DB: get_db, init_db, migraciones
  auth/                 # Login, logout, roles
  patients/             # Rutas, modelos SQL y servicios de pacientes
  charts/               # Dashboard, estadísticas, gráficos matplotlib
  utils/                # Helpers de edad y soporte ventilatorio
templates/              # Jinja2 (extienden base.html)
static/
  css/                  # base.css, patients.css, dashboard.css
  js/                   # date_picker.js, trajectory.js
```

## Stack

- [Flask](https://flask.palletsprojects.com/) — framework web
- [Flask-Login](https://flask-login.readthedocs.io/) — autenticación
- [SQLite3](https://docs.python.org/3/library/sqlite3.html) — base de datos
- [Matplotlib](https://matplotlib.org/) — generación de gráficos
- [Pandas](https://pandas.pydata.org/) — procesamiento de datos para exportación
- [livereload](https://livereload.readthedocs.io/) — hot reload en desarrollo

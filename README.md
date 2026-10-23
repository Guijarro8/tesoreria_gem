# Proyecto de Tesorería GEM

Aplicación de Streamlit para transformar extractos bancarios de Excel y actualizar
las hojas de cálculo de tesorería del GEM.

## Características

- Carga archivos `.xls` y normaliza los movimientos bancarios.
- Clasifica cuotas, gastos y movimientos varios.
- Calcula las cuotas pagadas por cada socio.
- Sustituye las cuatro primeras hojas de una hoja de cálculo de Google Sheets.
- Muestra el resultado en una interfaz web desplegada con Streamlit.

## Requisitos

- Python 3.13
- Una cuenta de servicio de Google con acceso a la hoja de cálculo
- [uv](https://docs.astral.sh/uv/#installation)

## Configuración local

Instala las dependencias y crea el entorno gestionado por uv:

```bash
uv sync
```

Crea `.streamlit/secrets.toml` con la clave de la hoja y las credenciales de la
cuenta de servicio como una cadena JSON:

```toml
tesoreria_gem_key = "id_de_la_hoja_de_calculo"
gcp_credentials = """{"type": "service_account", "project_id": "...", ...}"""
```

`.streamlit/` está excluido de Git. No publiques credenciales reales en el repositorio.

Puedes convertir el archivo JSON descargado de Google Cloud a una sola línea con:

```bash
python -c 'import json; print(json.dumps(json.load(open("credentials.json"))))'
```

## Ejecución

```bash
uv run streamlit run main.py
```

## Calidad del código

El proyecto usa Ruff para linting y formato, ty para comprobación de tipos y pytest
para las pruebas unitarias. Instala los hooks una vez por checkout:

```bash
uv run pre-commit install
```

Comandos disponibles:

```bash
uv run pre-commit run --all-files
uv run ruff check .
uv run ruff format --check .
uv run ty check .
uv run pytest
```

Ruff y ty se ejecutan también automáticamente antes de cada commit, junto con las
pruebas unitarias.

## Estructura

```text
main.py                  Interfaz de Streamlit
drag_drop/constants.py   Cuotas y nombres de columnas
drag_drop/utils.py       Procesamiento de Excel y publicación en Google Sheets
tests/                   Pruebas unitarias de las transformaciones
```

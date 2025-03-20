# Proyecto de Tesorería GEM

Este proyecto utiliza Streamlit para crear una interfaz de usuario que permite actualizar una hoja de cálculo de Google Sheets con datos de tesorería del GEM.

## Características

- **Interfaz Intuitiva**: Utiliza Streamlit para crear una interfaz de usuario sencilla y fácil de usar.
- **Actualización de datos**: Los datos se actualizan en  en Google Sheets.
- **Visualización de Datos**: Muestra gráficos y tablas para una mejor comprensión de tesorería

## Requisitos

- Python 
- Librerías en requirements.txt
- Cuenta de Google con acceso a Google Sheets


## Cómo colaborar

### Instalación

Usamos [uv](https://docs.astral.sh/uv/#installation) para manejar el repositorio.
Una vez instalado, crea un entorno virtual, actívalo e instala las dependencias:

```bash
uv venv
source .venv/bin/activate
uv sync
```

Usamos [ruff](https://astral.sh/ruff) como linter y formateador. Aconsejamos también
el uso de `pre-commit` para aplicar `ruff` automáticamente antes de hacer un commit.
`pre-commit` se instala automáticamente al hacer `uv sync` pero hay que instalar los
hooks manualmente:

```bash
pre-commit install
```

### Secretos

Crea un archivo `.streamlit/secrets.toml` con el siguiente contenido:

```toml
tesoreria_gem_key="id_de_la_hoja_de_calculo"
gcp_credentials="""credenciales_en_formato_json""" # Importante usar comillas triples
```

Para convertir un archivo de credenciales de Google Cloud a un string que se pueda
usar en un archivo `.toml`, puedes usar el siguiente script:

```python
import json

credentials_file = "path/to/credentials.json"
with open(credentials_file, "r") as f:
    credentials = json.load(f)

print(json.dumps(credentials))
```

### Ejecución

```bash
streamlit run dragdrop_tesoreria_data.py
```

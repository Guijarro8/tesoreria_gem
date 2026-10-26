# Proyecto de Tesorería GEM

Aplicación de Streamlit para transformar extractos bancarios de Excel y actualizar
las hojas de cálculo de tesorería del GEM.

El repositorio también incluye una aplicación independiente para crear facturas
de reservas y archivarlas en Google Drive.

## Características

- Carga archivos `.xls` y normaliza los movimientos bancarios.
- Clasifica cuotas, gastos y movimientos varios.
- Cruza las transferencias con un directorio privado de socios y alias.
- Calcula las cuotas pagadas por cada socio, consolidando nombres alternativos.
- Excluye socios inactivos, antiguos y pagos únicos sospechosos.
- Genera un informe financiero dinámico con resumen, evolución mensual y los
  quince gastos principales de la categoría `Otros`.
- Agrupa gastos en alquiler, electricidad, comisiones bancarias, seguros y otros.
- Muestra el porcentaje de ingresos aportado por cuotas y otros ingresos.
- Muestra el porcentaje que representa cada categoría sobre el gasto total.
- Excluye de todos los cálculos los movimientos del proyecto Marshill.
- Sustituye únicamente las hojas de salida `Cuotas` y `General`.
- Muestra el resultado en una interfaz web desplegada con Streamlit.

## Requisitos

- Python 3.13
- Una cuenta de servicio de Google con acceso a la hoja de salida
- Un Google Sheet privado con el directorio de socios, compartido como lector
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
tesoreria_members_key = "id_del_directorio_de_socios"
gcp_credentials = """{"type": "service_account", "project_id": "...", ...}"""
```

`.streamlit/` está excluido de Git. No publiques credenciales reales en el repositorio.

Puedes convertir el archivo JSON descargado de Google Cloud a una sola línea con:

```bash
python -c 'import json; print(json.dumps(json.load(open("credentials.json"))))'
```

## Directorio privado de socios

El directorio es un Google Sheet independiente que la aplicación solo lee. Comparte
el archivo con la cuenta de servicio como **Lector**. No copies nombres, alias ni
extractos reales al repositorio; `private/` está excluido de Git.

### Hoja `Socios`

Usa una fila por socio:

| Nombre | Estado | Alias 1 | Alias 2 | Alias 3 | Notas |
| --- | --- | --- | --- | --- | --- |
| Nombre canónico | activo | nombre observado en una transferencia | otra variante | | |

- Escribe el nombre que quieres mostrar en `Nombre`.
- Añade cada variante conocida en una columna `Alias`.
- Usa `activo` o `inactivo` en `Estado`.
- Para añadir un socio, inserta una fila completa. No hace falta ejecutar scripts.
- La aplicación reconoce automáticamente cualquier columna cuyo nombre empiece
  por `Alias`, por lo que se pueden añadir más columnas si fueran necesarias.
- No puede haber dos socios con el mismo nombre normalizado, ni un alias asignado
  a dos socios.
- Un alias que se parezca demasiado al nombre o alias de otro socio se bloquea
  para revisión, aunque esté escrito como una coincidencia exacta.

### Hoja `Ajustes`

| Parámetro | Valor |
| --- | --- |
| Meses para considerar inactivo | 12 |
| Meses de gracia para pago único | 3 |

La fecha de referencia es la última transacción del extracto cargado. Un pago
único solo cuenta si tiene tres meses o menos. La aplicación avisa de las
transferencias sin identificar, los alias ambiguos o pertenecientes probablemente
a otro socio y los socios excluidos.

## Informe financiero

La primera actualización crea una hoja `Informe` en la segunda posición de la
hoja de cálculo de salida. Sus fórmulas leen directamente de `General` y se
recalculan automáticamente cuando se actualizan los movimientos.

Para explorar otro periodo:

1. Cambia las fechas de las celdas `B4` (`Desde`) y `B5` (`Hasta`) directamente
   en Google Sheets.
2. El resumen, la evolución mensual y los quince gastos principales de `Otros`
   se actualizan sin ejecutar Streamlit.

El rango respeta las fechas exactas de `Desde` y `Hasta`, incluidos los meses
parciales. La tabla mensual admite hasta 120 meses desde la fecha `Desde`. Los
importes de la sección de principales gastos se muestran como negativos para
distinguirlos de los ingresos.

El ranking de los quince gastos principales de `Otros` aparece a la derecha del
resumen y del desglose por categorías, antes del detalle mensual, para que todo
sea visible sin recorrer la tabla de evolución.

Las columnas de porcentaje están junto a los importes correspondientes. Si la
hoja se actualiza desde una versión anterior, la migración copia los formatos
existentes a las nuevas columnas en lugar de reconstruir la hoja y perder colores,
bordes o negritas.

La clasificación de gastos se calcula al procesar los movimientos y se guarda en
la columna `categoria_gasto` de `General`. Los dos conceptos de Canal
de Isabel II se distinguen antes de normalizar la puntuación: el alquiler por su
concepto y el importe fijo de 372,23 €, y la electricidad por el concepto sin esa
puntuación. Las comisiones bancarias se detectan por `comision` y los seguros por
`seguros helvetia`; el resto se agrupa como `Otros`.

## Proyecto Marshill (Sudáfrica)

La hoja `Marshill (Sudáfrica)` es un registro persistente que la aplicación solo
lee. No se borra al volver a procesar el extracto.

Para excluir una operación:

1. Procesa el extracto para que las filas aparezcan en `General`. Cada fila
   incluye un `id_movimiento` estable y sus referencias bancarias.
2. Copia la fila completa desde `General`.
3. Pégala en `Marshill (Sudáfrica)`, respetando el mismo orden de columnas.
4. Añade cualquier aclaración en la columna `notas`.

La siguiente actualización eliminará esas operaciones antes del matching de
socios, la clasificación de gastos, los cálculos de cuotas y las fórmulas de
`Informe`. El resumen de procesamiento muestra cuántos movimientos se excluyeron,
los importes de ingresos y gastos, y los identificadores que ya no aparecen en el
extracto actual.

## Ejecución

```bash
uv run streamlit run main.py
```

La aplicación pública de facturas se ejecuta en un proceso independiente:

```bash
uv run streamlit run invoice_app.py
```

Ambas aplicaciones usan la misma cuenta de servicio, configurada en
`gcp_credentials`. La carpeta raíz se puede sobreescribir con el secreto opcional
`invoice_root_folder_id`; por defecto se usa la carpeta `2 IVA`.

## Facturas

El formulario permite elegir entre dos tipos:

- `Reserva`: usa los datos del grupo, fechas, refugio, participantes y cuota.
- `Libre`: permite indicar una fecha de factura, razón social, datos fiscales,
  descripción, importe total con IVA incluido, tipo de IVA y el nombre
  personalizado de la carpeta y del PDF.

Ambos tipos usan el mismo diseño, logotipo, sello y firma. El número de factura
sigue siendo automático y se antepone al nombre personalizado en las facturas
libres.

La app crea una única carpeta dentro de:

```text
2 IVA/<año>/GEM IVA <trimestre>T <año>/Facturas emitidas (ingresos)/
```

La app genera exclusivamente un PDF. No guarda un XLSX editable. El documento
parte de `assets/invoice_template.pdf`, una plantilla sin datos personales
derivada de las facturas históricas. Conserva el diseño original, el logotipo,
el sello, la firma y la distribución exacta de los campos.

En las facturas de reserva, el importe se calcula como:

```text
noches × participantes × cuota por participante
```

La cuota introducida incluye IVA. La base imponible y la cuota de IVA se
desglosan en el documento. Las reservas de un solo día se facturan como una
noche para evitar documentos de importe cero.

Las descripciones de las facturas libres conservan sus retornos de carro,
admitiendo hasta ocho líneas. Si el texto es largo, la app reduce automáticamente
el tamaño de fuente para mantenerlo dentro del diseño original.

Antes de crear una carpeta, la app calcula un hash no reversible de los datos y
lo guarda en las propiedades privadas de la carpeta de Drive. Si se repite la
operación, se muestra el número y el enlace de la factura existente en vez de
crear otra.

La carpeta raíz debe permanecer en acceso restringido. Los enlaces devueltos no
conceden permisos por sí solos: cada persona que los abra debe ser socio GEM con
acceso a la carpeta compartida.

Para regenerar directamente la hoja de producción con el extracto más reciente
guardado en `private/`:

```bash
uv run python -m scripts.regenerate_production
```

También se puede indicar un archivo concreto:

```bash
uv run python -m scripts.regenerate_production private/extracto.xls
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
invoice_app.py           Formulario público de facturas de reservas
invoicing/               Validación, numeración, PDF y acceso a Drive
assets/                  Plantilla PDF, logotipo e imagen de sello y firma
drag_drop/constants.py   Cuotas y nombres de columnas
drag_drop/members.py     Lectura y validación del directorio privado
drag_drop/utils.py       Procesamiento de Excel y publicación en Google Sheets
tests/                   Pruebas unitarias de las transformaciones
drag_drop/finance_report.py  Generación de la hoja Informe basada en fórmulas
drag_drop/expenses.py     Clasificación de gastos para el informe
drag_drop/exclusions.py   Exclusiones persistentes de proyectos
```

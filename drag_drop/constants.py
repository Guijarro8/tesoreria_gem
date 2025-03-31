"""Constants"""

# Cuotas a lo largo de los años: media cuota, cuota antigua y cuota actual
CUOTAS = {15, 25, 30}

# Nombres bonitos para columnas, por nombre de DataFrame
COLUMNS_RENAME = {
    "raw": {
        "F. Operativa": "fecha",
        "Concepto": "concepto",
        "Importe": "importe",
        "Saldo": "saldo",
    },
    "cuotas": {
        "concepto": "Concepto",
        "numero_cuotas_pagadas": "Cuotas Pagadas",
        "importe_pagado_total": "Total",
    },
}

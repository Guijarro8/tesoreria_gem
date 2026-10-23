"""Configuration values shared by the treasury data processing functions."""

# Cuotas a lo largo de los años: media cuota, cuota antigua y cuota actual
CUOTAS: frozenset[int] = frozenset({15, 25, 30})

# Nombres bonitos para columnas, por nombre de DataFrame
COLUMNS_RENAME: dict[str, dict[str, str]] = {
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

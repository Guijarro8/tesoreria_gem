"""Configuration values shared by the treasury data processing functions."""

# Cuotas a lo largo de los años: media cuota, cuota antigua y cuota actual
CUOTAS: frozenset[int] = frozenset({15, 25, 30})

MEMBER_DIRECTORY_TAB = "Socios"
MEMBER_SETTINGS_TAB = "Ajustes"
GENERAL_MOVEMENTS_TAB = "General"
FINANCE_REPORT_TAB = "Informe"

DEFAULT_INACTIVE_AFTER_MONTHS = 12
DEFAULT_SINGLE_PAYMENT_GRACE_MONTHS = 3
ALIAS_CONFLICT_THRESHOLD = 0.92

SETTING_INACTIVE_AFTER_MONTHS = "Meses para considerar inactivo"
SETTING_SINGLE_PAYMENT_GRACE_MONTHS = "Meses de gracia para pago único"

# Nombres bonitos para columnas, por nombre de DataFrame
COLUMNS_RENAME: dict[str, dict[str, str]] = {
    "raw": {
        "F. Operativa": "fecha",
        "Concepto": "concepto",
        "Importe": "importe",
        "Saldo": "saldo",
    },
    "cuotas": {
        "miembro": "Nombre",
        "numero_cuotas_pagadas": "Cuotas Pagadas",
        "importe_pagado_total": "Total",
    },
}

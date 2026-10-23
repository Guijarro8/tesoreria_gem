"""Configuration values shared by the treasury data processing functions."""

# Cuotas a lo largo de los años: media cuota, cuota antigua y cuota actual
CUOTAS: frozenset[int] = frozenset({15, 25, 30})

MEMBER_DIRECTORY_TAB = "Socios"
MEMBER_SETTINGS_TAB = "Ajustes"
GENERAL_MOVEMENTS_TAB = "General"
FINANCE_REPORT_TAB = "Informe"
PROJECT_EXCLUSIONS_TAB = "Marshill (Sudáfrica)"

DEFAULT_INACTIVE_AFTER_MONTHS = 12
DEFAULT_SINGLE_PAYMENT_GRACE_MONTHS = 3
ALIAS_CONFLICT_THRESHOLD = 0.92

SETTING_INACTIVE_AFTER_MONTHS = "Meses para considerar inactivo"
SETTING_SINGLE_PAYMENT_GRACE_MONTHS = "Meses de gracia para pago único"
EXPENSE_CATEGORY_COLUMN = "categoria_gasto"
EXPENSE_RENT = "Alquiler"
EXPENSE_ELECTRICITY = "Electricidad"
EXPENSE_BANK_FEES = "Comisiones bancarias"
EXPENSE_INSURANCE = "Seguros"
EXPENSE_OTHER = "Otros"
MOVEMENT_ID_COLUMN = "id_movimiento"

OUTPUT_WORKSHEET_TABS = {
    "cuotas": "Cuotas",
    "general": "General",
    "gasto": "Gastos",
    "varios": "Tabla dinámica 2",
}

# Nombres bonitos para columnas, por nombre de DataFrame
COLUMNS_RENAME: dict[str, dict[str, str]] = {
    "raw": {
        "F. Operativa": "fecha",
        "Concepto": "concepto",
        "Importe": "importe",
        "Saldo": "saldo",
        "Referencia 1": "referencia_1",
        "Referencia 2": "referencia_2",
    },
    "cuotas": {
        "miembro": "Nombre",
        "numero_cuotas_pagadas": "Cuotas Pagadas",
        "importe_pagado_total": "Total",
    },
}

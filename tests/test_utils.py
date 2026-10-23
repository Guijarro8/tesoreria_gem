"""Unit tests for workbook normalization and fee aggregation."""

from typing import cast
from unittest.mock import Mock

import gspread
import pandas as pd

from drag_drop import utils


def test_prepare_movements_normalizes_columns_and_classifies_rows() -> None:
    raw_movements = pd.DataFrame(
        {
            "F. Operativa": ["01/01/2024", "02/01/2024", "03/01/2024"],
            "Concepto": [
                "TRANSFERENCIA DE JUAN",
                "PAGO MATERIAL",
                "ABONO VARIOS",
            ],
            "Importe": [30, -12.5, 1],
            "Saldo": [1000, 987.5, 988.5],
        }
    )

    movements = utils.prepare_movements(raw_movements)

    assert movements["fecha"].dt.strftime("%Y-%m-%d").tolist() == [
        "2024-01-01",
        "2024-01-02",
        "2024-01-03",
    ]
    assert movements["mes_anio"].tolist() == ["2024-01", "2024-01", "2024-01"]
    assert movements["concepto"].tolist() == ["juan", "material", "varios"]
    assert movements["tipo"].tolist() == ["cuota", "gasto", "varios"]


def test_extract_cuotas_sums_payments_and_excludes_single_payments() -> None:
    movements = pd.DataFrame(
        {
            "concepto": ["ana", "ana", "luis", "luis", "marta"],
            "mes_anio": [
                "2024-01",
                "2024-02",
                "2024-01",
                "2024-02",
                "2024-01",
            ],
            "tipo": ["cuota"] * 5,
            "importe": [15, 15, 15, 25, 15],
        }
    )

    cuotas = utils.extract_cuotas(movements)

    assert cuotas["concepto"].tolist() == ["ana", "luis"]
    assert cuotas["importe_pagado_total"].tolist() == [30, 40]
    assert cuotas["numero_cuotas_pagadas"].tolist() == [2, 2]


def test_extract_cuotas_returns_an_empty_table_without_fee_data() -> None:
    movements = pd.DataFrame(
        {
            "concepto": pd.Series(dtype="str"),
            "mes_anio": pd.Series(dtype="str"),
            "tipo": pd.Series(dtype="str"),
            "importe": pd.Series(dtype="float64"),
        }
    )

    cuotas = utils.extract_cuotas(movements)

    assert cuotas.empty
    assert cuotas.columns.tolist() == [
        "concepto",
        "numero_cuotas_pagadas",
        "importe_pagado_total",
    ]


def test_upload_dataframes_places_fee_data_starting_at_b1() -> None:
    spreadsheet_mock = Mock()
    worksheet_mock = spreadsheet_mock.get_worksheet.return_value
    dataframes = {"cuotas": pd.DataFrame({"concepto": ["ana"]})}

    utils.upload_dataframes(
        dataframes,
        cast(gspread.Spreadsheet, spreadsheet_mock),
    )

    worksheet_mock.update.assert_called_once_with(
        [["Concepto"], ["ana"]],
        range_name="B1",
    )

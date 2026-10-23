"""Unit tests for workbook normalization, fee eligibility, and uploads."""

from typing import cast
from unittest.mock import Mock

import gspread
import pandas as pd

from drag_drop import constants, members, utils


def build_directory() -> members.MemberDirectory:
    member_rows: list[dict[str, object]] = [
        {"Nombre": "Synthetic Member A", "Estado": "activo", "Alias 1": "alias a"},
        {"Nombre": "Synthetic Member B", "Estado": "activo", "Alias 1": "alias b"},
        {"Nombre": "Synthetic Member C", "Estado": "activo", "Alias 1": "alias c"},
        {"Nombre": "Synthetic Member D", "Estado": "activo", "Alias 1": "alias d"},
        {
            "Nombre": "Synthetic Member E",
            "Estado": "inactivo",
            "Alias 1": "alias e",
        },
    ]
    settings_rows: list[dict[str, object]] = [
        {
            "Parámetro": constants.SETTING_INACTIVE_AFTER_MONTHS,
            "Valor": 12,
        },
        {
            "Parámetro": constants.SETTING_SINGLE_PAYMENT_GRACE_MONTHS,
            "Valor": 3,
        },
    ]
    return members.build_member_directory(member_rows, settings_rows)


def empty_matching_report() -> members.MatchingReport:
    return members.MatchingReport(
        matched_fee_payments=0,
        unmatched_aliases=(),
        ambiguous_aliases=(),
        suspicious_aliases=(),
    )


def test_prepare_movements_normalizes_columns_and_classifies_rows() -> None:
    raw_movements = pd.DataFrame(
        {
            "F. Operativa": ["01/01/2024", "02/01/2024", "03/01/2024"],
            "Concepto": [
                "TRANSFERENCIA DE SYNTHETIC MEMBER",
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
    assert movements["concepto"].tolist() == [
        "synthetic member",
        "material",
        "varios",
    ]
    assert movements["tipo"].tolist() == ["cuota", "gasto", "varios"]
    assert movements[constants.EXPENSE_CATEGORY_COLUMN].tolist() == [
        "",
        constants.EXPENSE_OTHER,
        "",
    ]


def test_extract_cuotas_applies_membership_and_activity_rules() -> None:
    movements = pd.DataFrame(
        {
            "fecha": pd.to_datetime(
                [
                    "2025-11-01",
                    "2025-12-01",
                    "2025-11-15",
                    "2025-08-01",
                    "2024-10-01",
                    "2024-11-30",
                    "2025-11-01",
                    "2025-12-01",
                    "2025-12-31",
                ]
            ),
            "miembro": [
                "Synthetic Member A",
                "Synthetic Member A",
                "Synthetic Member B",
                "Synthetic Member C",
                "Synthetic Member D",
                "Synthetic Member D",
                "Synthetic Member E",
                "Synthetic Member E",
                None,
            ],
            "tipo": ["cuota"] * 8 + ["varios"],
            "mes_anio": [
                "2025-11",
                "2025-12",
                "2025-11",
                "2025-08",
                "2024-10",
                "2024-11",
                "2025-11",
                "2025-12",
                "2025-12",
            ],
            "importe": [30] * 8 + [1],
        }
    )

    cuotas, report = utils.extract_cuotas(
        movements,
        build_directory(),
        empty_matching_report(),
    )

    assert cuotas["miembro"].tolist() == [
        "Synthetic Member A",
        "Synthetic Member B",
    ]
    assert cuotas["importe_pagado_total"].tolist() == [60, 30]
    assert cuotas["numero_cuotas_pagadas"].tolist() == [2, 1]
    assert report.excluded_inactive_members == ("Synthetic Member E",)
    assert report.excluded_old_single_payments == ("Synthetic Member C",)
    assert report.excluded_stale_members == ("Synthetic Member D",)


def test_extract_cuotas_returns_an_empty_table_without_eligible_payments() -> None:
    movements = pd.DataFrame(
        {
            "fecha": pd.Series(dtype="datetime64[ns]"),
            "miembro": pd.Series(dtype="str"),
            "tipo": pd.Series(dtype="str"),
            "mes_anio": pd.Series(dtype="str"),
            "importe": pd.Series(dtype="float64"),
        }
    )

    cuotas, report = utils.extract_cuotas(
        movements,
        build_directory(),
        empty_matching_report(),
    )

    assert cuotas.empty
    assert report.as_of is None
    assert list(cuotas.columns) == [
        "miembro",
        "numero_cuotas_pagadas",
        "importe_pagado_total",
    ]


def test_extract_cuotas_sorts_by_accent_insensitive_name_without_rewriting_it() -> None:
    member_rows: list[dict[str, object]] = [
        {
            "Nombre": "Zulu Synthetic",
            "Estado": "activo",
            "Alias 1": "zulu alias",
        },
        {
            "Nombre": "Álvaro Synthetic",
            "Estado": "activo",
            "Alias 1": "alvaro alias",
        },
    ]
    settings_rows: list[dict[str, object]] = [
        {
            "Parámetro": constants.SETTING_INACTIVE_AFTER_MONTHS,
            "Valor": 12,
        },
        {
            "Parámetro": constants.SETTING_SINGLE_PAYMENT_GRACE_MONTHS,
            "Valor": 3,
        },
    ]
    directory = members.build_member_directory(member_rows, settings_rows)
    movements = pd.DataFrame(
        {
            "fecha": pd.to_datetime(["2025-12-01", "2025-12-01"]),
            "miembro": ["Zulu Synthetic", "Álvaro Synthetic"],
            "tipo": ["cuota", "cuota"],
            "mes_anio": ["2025-12", "2025-12"],
            "importe": [30, 30],
        }
    )

    cuotas, _report = utils.extract_cuotas(
        movements,
        directory,
        empty_matching_report(),
    )

    assert cuotas["miembro"].tolist() == [
        "Álvaro Synthetic",
        "Zulu Synthetic",
    ]


def test_upload_dataframes_clears_and_writes_from_column_a() -> None:
    spreadsheet_mock = Mock()
    worksheet_mock = spreadsheet_mock.worksheet.return_value
    dataframes = {"cuotas": pd.DataFrame({"miembro": ["synthetic-a"]})}

    utils.upload_dataframes(
        dataframes,
        cast(gspread.Spreadsheet, spreadsheet_mock),
    )

    spreadsheet_mock.worksheet.assert_called_once_with("Cuotas")
    worksheet_mock.clear.assert_called_once_with()
    worksheet_mock.update.assert_called_once_with([["Nombre"], ["synthetic-a"]])

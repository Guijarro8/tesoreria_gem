"""Tests for the formula-driven finance report layout."""

from datetime import date
from typing import cast
from unittest.mock import Mock

import gspread
import pandas as pd
import pytest

from drag_drop import finance_report


def test_default_dates_cover_the_latest_twelve_months() -> None:
    movements = pd.DataFrame(
        {"fecha": pd.to_datetime(["2025-10-15", "2026-10-15", "2026-03-01"])}
    )

    start_date, end_date = finance_report.default_report_dates(movements)

    assert start_date == date(2025, 11, 1)
    assert end_date == date(2026, 10, 15)


def test_report_layout_uses_dynamic_date_and_month_formulas() -> None:
    values = finance_report.build_report_values(
        date(2025, 11, 1),
        date(2026, 10, 15),
    )

    assert values[3] == ["Desde", "=DATE(2025,11,1)"]
    assert values[4] == ["Hasta", "=DATE(2026,10,15)"]
    assert values[6][4] == "Top 15 gastos"
    assert values[7][4:] == ["Fecha", "Concepto", "Importe (negativo)"]
    assert values[8][1] == "=SUM(B27:B146)"
    assert values[8][2] == "=IFERROR(B9/B11,0)"
    assert "limit 15" in str(values[8][4])
    assert values[16][0] == "Alquiler"
    assert values[16][2] == "=IFERROR(B17/$B$12,0)"
    assert values[25][0] == "Mes"
    assert str(values[26][0]).startswith("=TEXT(DATE(YEAR($B$4)")
    assert len(values) == finance_report.MONTH_TABLE_END_ROW


def test_spanish_locale_uses_semicolon_formula_separators() -> None:
    assert finance_report.formula_separator("es_ES") == ";"
    assert finance_report.formula_separator("en_US") == ","

    values = finance_report.build_report_values(
        date(2025, 11, 1),
        date(2026, 10, 15),
        separator=";",
    )

    assert values[3][1] == "=DATE(2025;11;1)"
    assert "SUMIFS(" in str(values[26][1])
    assert ';"cuota";' in str(values[26][1])


def test_report_rejects_reversed_date_ranges() -> None:
    with pytest.raises(ValueError, match="start date"):
        finance_report.build_report_values(
            date(2026, 10, 15),
            date(2025, 11, 1),
        )


def test_existing_report_is_not_recreated() -> None:
    spreadsheet_mock = Mock()
    existing = spreadsheet_mock.worksheet.return_value
    existing.row_count = 200
    existing.col_count = 11
    spreadsheet_mock.worksheets.return_value = [existing]

    result = finance_report.ensure_finance_report_sheet(
        cast(gspread.Spreadsheet, spreadsheet_mock),
        pd.DataFrame({"fecha": pd.to_datetime(["2026-10-15"])}),
    )

    assert result is existing
    existing.update_index.assert_called_once_with(0)
    spreadsheet_mock.add_worksheet.assert_not_called()

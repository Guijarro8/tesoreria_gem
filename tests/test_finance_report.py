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
    assert values[8][1] == "=SUM(B18:B137)"
    assert values[16][0] == "Mes"
    assert str(values[17][0]).startswith("=TEXT(DATE(YEAR($B$4)")
    assert len(values) == finance_report.TOP_EXPENSES_FIRST_ROW
    assert "QUERY(" in str(values[-1][0])
    assert "limit 10" in str(values[-1][0])


def test_spanish_locale_uses_semicolon_formula_separators() -> None:
    assert finance_report.formula_separator("es_ES") == ";"
    assert finance_report.formula_separator("en_US") == ","

    values = finance_report.build_report_values(
        date(2025, 11, 1),
        date(2026, 10, 15),
        separator=";",
    )

    assert values[3][1] == "=DATE(2025;11;1)"
    assert "SUMIFS(" in str(values[17][1])
    assert ';"cuota";' in str(values[17][1])


def test_report_rejects_reversed_date_ranges() -> None:
    with pytest.raises(ValueError, match="start date"):
        finance_report.build_report_values(
            date(2026, 10, 15),
            date(2025, 11, 1),
        )


def test_existing_report_is_not_recreated() -> None:
    spreadsheet_mock = Mock()
    existing = spreadsheet_mock.worksheet.return_value

    result = finance_report.ensure_finance_report_sheet(
        cast(gspread.Spreadsheet, spreadsheet_mock),
        pd.DataFrame({"fecha": pd.to_datetime(["2026-10-15"])}),
    )

    assert result is existing
    spreadsheet_mock.add_worksheet.assert_not_called()

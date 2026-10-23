"""Tests for persistent project exclusion handling."""

from typing import cast
from unittest.mock import Mock

import gspread
import pandas as pd

from drag_drop import constants, exclusions


def test_apply_exclusions_removes_expenses_and_income_before_other_processing() -> None:
    movements = pd.DataFrame(
        {
            constants.MOVEMENT_ID_COLUMN: [
                "project-expense",
                "project-income",
                "normal-income",
            ],
            "importe": [-120.0, 250.0, 30.0],
            "tipo": ["gasto", "varios", "cuota"],
        }
    )

    included, report = exclusions.apply_exclusions(
        movements,
        {"project-expense", "project-income", "missing"},
    )

    assert included[constants.MOVEMENT_ID_COLUMN].tolist() == ["normal-income"]
    assert report.configured_ids == 3
    assert report.matched_transactions == 2
    assert report.unmatched_ids == ("missing",)
    assert report.excluded_income == 250.0
    assert report.excluded_expenses == 120.0


def test_without_exclusions_movements_are_unchanged() -> None:
    movements = pd.DataFrame(
        {
            constants.MOVEMENT_ID_COLUMN: ["first", "second"],
            "importe": [10.0, -5.0],
        }
    )

    included, report = exclusions.apply_exclusions(movements, frozenset())

    assert included is movements
    assert report.configured_ids == 0
    assert report.matched_transactions == 0


def test_existing_exclusion_sheet_is_never_rewritten() -> None:
    spreadsheet_mock = Mock()
    worksheet_mock = spreadsheet_mock.worksheet.return_value

    result = exclusions.ensure_exclusion_sheet(
        cast(gspread.Spreadsheet, spreadsheet_mock),
    )

    assert result is worksheet_mock
    spreadsheet_mock.add_worksheet.assert_not_called()
    worksheet_mock.clear.assert_not_called()
    worksheet_mock.update.assert_not_called()


def test_exclusion_sheet_uses_marshill_name_and_transaction_id() -> None:
    spreadsheet_mock = Mock()
    spreadsheet_mock.worksheet.side_effect = gspread.WorksheetNotFound(
        constants.PROJECT_EXCLUSIONS_TAB
    )
    spreadsheet_mock.worksheets.return_value = [Mock(), Mock(), Mock()]
    worksheet_mock = spreadsheet_mock.add_worksheet.return_value

    result = exclusions.ensure_exclusion_sheet(
        cast(gspread.Spreadsheet, spreadsheet_mock),
    )

    assert result is worksheet_mock
    spreadsheet_mock.add_worksheet.assert_called_once_with(
        title="Marshill (Sudáfrica)",
        rows=500,
        cols=12,
        index=2,
    )
    worksheet_mock.update.assert_called_once_with(
        [exclusions.EXCLUSION_SHEET_HEADERS],
        range_name="A1",
    )

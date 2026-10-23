"""Persist and apply project-specific bank transaction exclusions."""

from __future__ import annotations

from collections.abc import Set
from dataclasses import dataclass
from typing import cast

import gspread
import pandas as pd

from . import constants

EXCLUSION_SHEET_HEADERS = [
    "fecha",
    "concepto",
    "importe",
    "saldo",
    "mes_anio",
    "tipo",
    constants.EXPENSE_CATEGORY_COLUMN,
    "miembro",
    "referencia_1",
    "referencia_2",
    constants.MOVEMENT_ID_COLUMN,
    "notas",
]


@dataclass(frozen=True)
class ExclusionReport:
    """Reconciliation details for project transactions excluded from all totals."""

    configured_ids: int
    matched_transactions: int
    unmatched_ids: tuple[str, ...]
    excluded_income: float
    excluded_expenses: float


def ensure_exclusion_sheet(spreadsheet: gspread.Spreadsheet) -> gspread.Worksheet:
    """Create the editable exclusion ledger once and never overwrite it."""
    try:
        return spreadsheet.worksheet(constants.PROJECT_EXCLUSIONS_TAB)
    except gspread.WorksheetNotFound:
        worksheets = spreadsheet.worksheets()
        worksheet = spreadsheet.add_worksheet(
            title=constants.PROJECT_EXCLUSIONS_TAB,
            rows=500,
            cols=len(EXCLUSION_SHEET_HEADERS),
            index=2 if len(worksheets) > 2 else len(worksheets),
        )
        worksheet.update([EXCLUSION_SHEET_HEADERS], range_name="A1")
        worksheet.format(
            "A1:L1",
            {
                "backgroundColor": {"red": 0.12, "green": 0.31, "blue": 0.47},
                "textFormat": {
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                    "bold": True,
                },
            },
        )
        worksheet.freeze(rows=1)
        return worksheet


def load_exclusion_ids(spreadsheet: gspread.Spreadsheet) -> frozenset[str]:
    """Read the user-maintained transaction IDs from the exclusion ledger."""
    worksheet = ensure_exclusion_sheet(spreadsheet)
    values = cast(list[list[str]], worksheet.get_all_values())
    if not values:
        return frozenset[str]()

    headers = values[0]
    if constants.MOVEMENT_ID_COLUMN not in headers:
        raise ValueError("The exclusion sheet is missing id_movimiento.")
    id_index = headers.index(constants.MOVEMENT_ID_COLUMN)

    return frozenset(
        row[id_index].strip()
        for row in values[1:]
        if len(row) > id_index and row[id_index].strip()
    )


def apply_exclusions(
    movements: pd.DataFrame,
    excluded_ids: Set[str],
) -> tuple[pd.DataFrame, ExclusionReport]:
    """Remove excluded transactions before any other financial calculation."""
    excluded_id_set = set(excluded_ids)
    if not excluded_id_set:
        report = ExclusionReport(
            configured_ids=0,
            matched_transactions=0,
            unmatched_ids=(),
            excluded_income=0.0,
            excluded_expenses=0.0,
        )
        return movements, report

    match_mask = movements[constants.MOVEMENT_ID_COLUMN].isin(excluded_id_set)
    excluded = movements.loc[match_mask].copy()
    included = movements.loc[~match_mask].copy()
    matched_ids = set(excluded[constants.MOVEMENT_ID_COLUMN].astype(str))
    amounts = pd.to_numeric(excluded["importe"], errors="coerce").fillna(0.0)

    report = ExclusionReport(
        configured_ids=len(excluded_id_set),
        matched_transactions=len(excluded),
        unmatched_ids=tuple(sorted(excluded_id_set - matched_ids)),
        excluded_income=float(amounts[amounts > 0].sum()),
        excluded_expenses=float(-amounts[amounts < 0].sum()),
    )
    return cast(pd.DataFrame, included), report

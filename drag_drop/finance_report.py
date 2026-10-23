"""Build a formula-driven financial report inside the output spreadsheet."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

import gspread
import pandas as pd

from . import constants

EXPENSE_CATEGORIES = (
    constants.EXPENSE_RENT,
    constants.EXPENSE_ELECTRICITY,
    constants.EXPENSE_BANK_FEES,
    constants.EXPENSE_INSURANCE,
    constants.EXPENSE_OTHER,
)

CATEGORY_SECTION_ROW = 15
CATEGORY_HEADER_ROW = 16
CATEGORY_FIRST_ROW = 17

TOP_EXPENSES_SECTION_ROW = 7
TOP_EXPENSES_HEADER_ROW = 8
TOP_EXPENSES_FIRST_ROW = 9

MONTH_TABLE_SECTION_ROW = 25
MONTH_TABLE_HEADER_ROW = MONTH_TABLE_SECTION_ROW + 1
MONTH_TABLE_START_ROW = MONTH_TABLE_HEADER_ROW + 1
MONTH_TABLE_ROWS = 120
MONTH_TABLE_END_ROW = MONTH_TABLE_START_ROW + MONTH_TABLE_ROWS - 1


def formula_separator(locale: str) -> str:
    """Return the formula argument separator for common spreadsheet locales."""
    if locale.startswith(("de_", "es_", "fr_", "it_", "pt_")):
        return ";"
    return ","


def default_report_dates(movements: pd.DataFrame) -> tuple[date, date]:
    """Return the first day of the earliest month and the latest movement date."""
    dates = pd.to_datetime(movements["fecha"], errors="coerce").dropna()
    if dates.empty:
        raise ValueError("Cannot build a report without dated movements.")

    latest = cast(pd.Timestamp, dates.max())
    start_period = cast(pd.Period, latest.to_period("M") - (12 - 1))
    return start_period.start_time.date(), latest.date()


def build_report_values(
    start_date: date,
    end_date: date,
    separator: str = ",",
) -> list[list[object]]:
    """Return the user-entered values and formulas for the Informe worksheet."""
    if start_date > end_date:
        raise ValueError("Report start date must not be after end date.")

    general = f"'{constants.GENERAL_MOVEMENTS_TAB}'"
    month_start = f'TEXT($B$4{separator}"YYYY-MM")'
    month_end = f'TEXT($B$5{separator}"YYYY-MM")'
    category_columns = dict(
        zip(EXPENSE_CATEGORIES, ("G", "H", "I", "J", "K"), strict=True)
    )
    query_text = (
        "\"select A, B, C where F = 'gasto' "
        "and E >= '\"&"
        f"{month_start}&"
        "\"' and E <= '\"&"
        f"{month_end}&"
        '"\' order by C asc limit 15"'
    )
    top_expenses_formula = (
        f"=IFERROR(QUERY({general}!$A$2:$H{separator}{query_text}"
        f'{separator}0){separator}"Sin gastos")'
    )

    values: list[list[object]] = [
        ["Informe financiero GEM"],
        [
            "El rango se aplica por meses completos. "
            "Edita Desde y Hasta para actualizar el informe."
        ],
        [],
        [
            "Desde",
            f"=DATE({start_date.year}{separator}{start_date.month}"
            f"{separator}{start_date.day})",
        ],
        [
            "Hasta",
            f"=DATE({end_date.year}{separator}{end_date.month}"
            f"{separator}{end_date.day})",
        ],
        [],
        ["Resumen del periodo", "", "", "Top 15 gastos"],
        ["Indicador", "Importe", "", "Fecha", "Concepto", "Importe (negativo)"],
        [
            "Cuotas de socios",
            f"=SUM(B{MONTH_TABLE_START_ROW}:B{MONTH_TABLE_END_ROW})",
            "",
            top_expenses_formula,
        ],
        [
            "Otros ingresos",
            f"=SUM(C{MONTH_TABLE_START_ROW}:C{MONTH_TABLE_END_ROW})",
        ],
        ["Ingresos totales", "=B9+B10"],
        [
            "Gastos",
            f"=SUM(E{MONTH_TABLE_START_ROW}:E{MONTH_TABLE_END_ROW})",
        ],
        ["Balance neto", "=B11-B12"],
        [],
        ["Gastos por tipo"],
        ["Categoría", "Importe"],
    ]
    values.extend(
        [
            category,
            (
                f"=SUM({category_columns[category]}{MONTH_TABLE_START_ROW}:"
                f"{category_columns[category]}{MONTH_TABLE_END_ROW})"
            ),
        ]
        for category in EXPENSE_CATEGORIES
    )

    values.extend(
        [
            *[[] for _ in range(3)],
            ["Evolución mensual"],
            [
                "Mes",
                "Cuotas",
                "Otros ingresos",
                "Ingresos totales",
                "Gastos",
                "Balance",
                *EXPENSE_CATEGORIES,
            ],
        ]
    )

    for offset in range(MONTH_TABLE_ROWS):
        row_number = MONTH_TABLE_START_ROW + offset
        previous_row = row_number - 1
        if offset == 0:
            month_formula = (
                f"=TEXT(DATE(YEAR($B$4){separator}MONTH($B$4)"
                f'{separator}1){separator}"YYYY-MM")'
            )
        else:
            month_formula = (
                f'=IF($A{previous_row}=""{separator}""{separator}'
                f'IF($A{previous_row}>={month_end}{separator}""{separator}'
                f"TEXT(EDATE(DATE(VALUE(LEFT($A{previous_row}{separator}4))"
                f"{separator}VALUE(RIGHT($A{previous_row}{separator}2))"
                f'{separator}1){separator}1){separator}"YYYY-MM")))'
            )

        values.append(
            [
                month_formula,
                (
                    f'=IF($A{row_number}=""{separator}""{separator}'
                    f"SUMIFS({general}!$C$2:$C{separator}"
                    f'{general}!$F$2:$F{separator}"cuota"{separator}'
                    f"{general}!$E$2:$E{separator}$A{row_number}))"
                ),
                (
                    f'=IF($A{row_number}=""{separator}""{separator}'
                    f"SUMIFS({general}!$C$2:$C{separator}"
                    f'{general}!$F$2:$F{separator}"varios"{separator}'
                    f'{general}!$C$2:$C{separator}">0"{separator}'
                    f"{general}!$E$2:$E{separator}$A{row_number}))"
                ),
                f'=IF($A{row_number}=""{separator}""{separator}'
                f"B{row_number}+C{row_number})",
                f'=IF($A{row_number}=""{separator}""{separator}'
                f"SUM(G{row_number}:K{row_number}))",
                f'=IF($A{row_number}=""{separator}""{separator}'
                f"D{row_number}-E{row_number})",
                *[
                    (
                        f'=IF($A{row_number}=""{separator}""{separator}'
                        f"-SUMIFS({general}!$C$2:$C{separator}"
                        f'{general}!$F$2:$F{separator}"gasto"{separator}'
                        f'{general}!$G$2:$G{separator}"{category}"'
                        f"{separator}{general}!$E$2:$E{separator}"
                        f"$A{row_number}))"
                    )
                    for category in EXPENSE_CATEGORIES
                ],
            ]
        )

    return values


def ensure_finance_report_sheet(
    spreadsheet: gspread.Spreadsheet,
    movements: pd.DataFrame,
    start_date: date | None = None,
    end_date: date | None = None,
    replace: bool = False,
) -> gspread.Worksheet:
    """Create the formula-driven report once, preserving later user date choices."""
    try:
        worksheet = spreadsheet.worksheet(constants.FINANCE_REPORT_TAB)
    except gspread.WorksheetNotFound:
        worksheets = spreadsheet.worksheets()
        target_index = 1 if len(worksheets) > 1 else 0
        worksheet = spreadsheet.add_worksheet(
            title=constants.FINANCE_REPORT_TAB,
            rows=200,
            cols=11,
            index=target_index,
        )
    else:
        target_index = 1 if len(spreadsheet.worksheets()) > 1 else 0
        worksheet.update_index(target_index)
        if not replace:
            _ensure_report_dimensions(worksheet)
            return worksheet

    if start_date is None or end_date is None:
        start_date, end_date = default_report_dates(movements)
    metadata = cast(dict[str, Any], spreadsheet.fetch_sheet_metadata())
    properties = cast(dict[str, Any], metadata.get("properties", {}))
    locale = str(properties.get("locale", ""))
    _ensure_report_dimensions(worksheet)
    worksheet.clear()
    worksheet.update(
        build_report_values(
            start_date,
            end_date,
            separator=formula_separator(locale),
        ),
        range_name="A1",
        raw=False,
    )
    _format_report(worksheet)
    return worksheet


def _ensure_report_dimensions(worksheet: gspread.Worksheet) -> None:
    if worksheet.row_count < 200:
        worksheet.add_rows(200 - worksheet.row_count)
    if worksheet.col_count < 11:
        worksheet.add_cols(11 - worksheet.col_count)


def _format_report(worksheet: gspread.Worksheet) -> None:
    title_format: dict[str, Any] = {
        "backgroundColor": {"red": 0.12, "green": 0.31, "blue": 0.47},
        "textFormat": {
            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            "bold": True,
        },
    }
    section_format: dict[str, Any] = {
        "backgroundColor": {"red": 0.85, "green": 0.92, "blue": 0.97},
        "textFormat": {"bold": True},
    }
    amount_format: dict[str, Any] = {
        "numberFormat": {"type": "CURRENCY", "pattern": '#,##0.00 "€"'}
    }
    worksheet.format("A1:K1", title_format)
    worksheet.format("A7:B8", section_format)
    worksheet.format("D7:F8", section_format)
    worksheet.format("A15:B16", section_format)
    worksheet.format(
        f"A{MONTH_TABLE_SECTION_ROW}:K{MONTH_TABLE_HEADER_ROW}",
        section_format,
    )
    worksheet.format("B4:B5", {"numberFormat": {"type": "DATE"}})
    worksheet.format("B9:B13", amount_format)
    worksheet.format(
        f"B{CATEGORY_FIRST_ROW}:B{CATEGORY_FIRST_ROW + len(EXPENSE_CATEGORIES) - 1}",
        amount_format,
    )
    worksheet.format(
        f"B{MONTH_TABLE_START_ROW}:K{MONTH_TABLE_END_ROW}",
        amount_format,
    )
    worksheet.format(
        f"F{TOP_EXPENSES_FIRST_ROW}:F{TOP_EXPENSES_FIRST_ROW + 14}",
        amount_format,
    )
    worksheet.freeze(rows=5)

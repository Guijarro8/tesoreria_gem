"""Build a formula-driven financial report inside the output spreadsheet."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

import gspread
import pandas as pd

from . import constants

MONTH_TABLE_ROWS = 120
MONTH_TABLE_START_ROW = 18
TOP_EXPENSES_SECTION_ROW = MONTH_TABLE_START_ROW + MONTH_TABLE_ROWS + 1
TOP_EXPENSES_HEADER_ROW = TOP_EXPENSES_SECTION_ROW + 1
TOP_EXPENSES_FIRST_ROW = TOP_EXPENSES_HEADER_ROW + 1


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
    final_month_row = MONTH_TABLE_START_ROW + MONTH_TABLE_ROWS - 1

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
        ["Resumen del periodo"],
        ["Indicador", "Importe"],
        [
            "Cuotas de socios",
            f"=SUM(B{MONTH_TABLE_START_ROW}:B{final_month_row})",
        ],
        [
            "Otros ingresos",
            f"=SUM(C{MONTH_TABLE_START_ROW}:C{final_month_row})",
        ],
        ["Ingresos totales", "=B9+B10"],
        [
            "Gastos",
            f"=SUM(E{MONTH_TABLE_START_ROW}:E{final_month_row})",
        ],
        ["Balance neto", "=B11-B12"],
        ["", ""],
        [],
        ["Evolución mensual"],
        ["Mes", "Cuotas", "Otros ingresos", "Ingresos totales", "Gastos", "Balance"],
    ]

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
                (
                    f'=IF($A{row_number}=""{separator}""{separator}'
                    f"-SUMIFS({general}!$C$2:$C{separator}"
                    f'{general}!$F$2:$F{separator}"gasto"{separator}'
                    f'{general}!$C$2:$C{separator}"<0"{separator}'
                    f"{general}!$E$2:$E{separator}$A{row_number}))"
                ),
                f'=IF($A{row_number}=""{separator}""{separator}'
                f"D{row_number}-E{row_number})",
            ]
        )

    query_text = (
        "\"select A, B, C where F = 'gasto' "
        "and E >= '\"&"
        f"{month_start}&"
        "\"' and E <= '\"&"
        f"{month_end}&"
        '"\' order by C asc limit 10"'
    )
    values.extend(
        [
            [],
            ["Top 10 gastos"],
            ["Fecha", "Concepto", "Importe (negativo)"],
            [
                f"=IFERROR(QUERY({general}!$A$2:$F{separator}{query_text}"
                f'{separator}0){separator}"Sin gastos")'
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
        worksheet = spreadsheet.add_worksheet(
            title=constants.FINANCE_REPORT_TAB,
            rows=160,
            cols=6,
        )
    else:
        if not replace:
            return worksheet

    if start_date is None or end_date is None:
        start_date, end_date = default_report_dates(movements)
    metadata = cast(dict[str, Any], spreadsheet.fetch_sheet_metadata())
    properties = cast(dict[str, Any], metadata.get("properties", {}))
    locale = str(properties.get("locale", ""))
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
    final_month_row = MONTH_TABLE_START_ROW + MONTH_TABLE_ROWS - 1
    final_expense_row = TOP_EXPENSES_FIRST_ROW + 9

    worksheet.format("A1:F1", title_format)
    worksheet.format("A7:F8", section_format)
    worksheet.format("A16:F17", section_format)
    worksheet.format(
        f"A{TOP_EXPENSES_SECTION_ROW}:C{TOP_EXPENSES_HEADER_ROW}",
        section_format,
    )
    worksheet.format("B4:B5", {"numberFormat": {"type": "DATE"}})
    worksheet.format("B9:B13", amount_format)
    worksheet.format(f"B{MONTH_TABLE_START_ROW}:F{final_month_row}", amount_format)
    worksheet.format(f"C{TOP_EXPENSES_FIRST_ROW}:C{final_expense_row}", amount_format)
    worksheet.freeze(rows=5)

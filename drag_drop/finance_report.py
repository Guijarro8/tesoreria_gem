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


def _top_expenses_formula(separator: str) -> str:
    general = f"'{constants.GENERAL_MOVEMENTS_TAB}'"
    filter_formula = (
        f"FILTER({general}!$A$2:$C{separator}"
        f'{general}!$F$2:$F{separator}"gasto"{separator}'
        f'{general}!$A$2:$A{separator}">="&$B$4{separator}'
        f'{general}!$A$2:$A{separator}"<="&$B$5)'
    )
    return (
        f"=IFERROR(SORTN({filter_formula}{separator}15{separator}"
        f'2{separator}3{separator}TRUE){separator}"Sin gastos")'
    )


def build_report_values(
    start_date: date,
    end_date: date,
    separator: str = ",",
) -> list[list[object]]:
    """Return the user-entered values and formulas for the Informe worksheet."""
    if start_date > end_date:
        raise ValueError("Report start date must not be after end date.")

    general = f"'{constants.GENERAL_MOVEMENTS_TAB}'"
    month_end = f'TEXT($B$5{separator}"YYYY-MM")'
    category_columns = dict(
        zip(EXPENSE_CATEGORIES, ("G", "H", "I", "J", "K"), strict=True)
    )
    top_expenses_formula = _top_expenses_formula(separator)

    values: list[list[object]] = [
        ["Informe financiero GEM"],
        [
            "El rango usa fechas exactas. "
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
        ["Resumen del periodo", "", "", "", "Top 15 gastos"],
        [
            "Indicador",
            "Importe",
            "Porcentaje",
            "",
            "Fecha",
            "Concepto",
            "Importe (negativo)",
        ],
        [
            "Cuotas de socios",
            f"=SUM(B{MONTH_TABLE_START_ROW}:B{MONTH_TABLE_END_ROW})",
            f"=IFERROR(B9/B11{separator}0)",
            "",
            top_expenses_formula,
        ],
        [
            "Otros ingresos",
            f"=SUM(C{MONTH_TABLE_START_ROW}:C{MONTH_TABLE_END_ROW})",
            f"=IFERROR(B10/B11{separator}0)",
        ],
        ["Ingresos totales", "=B9+B10", f"=IFERROR(B11/B11{separator}0)"],
        [
            "Gastos",
            f"=SUM(E{MONTH_TABLE_START_ROW}:E{MONTH_TABLE_END_ROW})",
            f"=IFERROR(B12/B11{separator}0)",
        ],
        ["Balance neto", "=B11-B12", f"=IFERROR(B13/B11{separator}0)"],
        [],
        ["Gastos por tipo", "", ""],
        ["Categoría", "Importe", "Porcentaje"],
    ]
    values.extend(
        [
            category,
            (
                f"=SUM({category_columns[category]}{MONTH_TABLE_START_ROW}:"
                f"{category_columns[category]}{MONTH_TABLE_END_ROW})"
            ),
            f"=IFERROR(B{CATEGORY_FIRST_ROW + index}/$B$12{separator}0)",
        ]
        for index, category in enumerate(EXPENSE_CATEGORIES)
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
        month_start = (
            f"DATE(VALUE(LEFT($A{row_number}{separator}4))"
            f"{separator}VALUE(RIGHT($A{row_number}{separator}2))"
            f"{separator}1)"
        )
        date_filter = (
            f'{general}!$A$2:$A{separator}">="&MAX($B$4{separator}{month_start})'
            f'{separator}{general}!$A$2:$A{separator}"<="&'
            f"MIN($B$5{separator}EOMONTH({month_start}{separator}0))"
        )
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
                    f"{date_filter}))"
                ),
                (
                    f'=IF($A{row_number}=""{separator}""{separator}'
                    f"SUMIFS({general}!$C$2:$C{separator}"
                    f'{general}!$F$2:$F{separator}"varios"{separator}'
                    f'{general}!$C$2:$C{separator}">0"{separator}'
                    f"{date_filter}))"
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
                        f"{separator}{date_filter}))"
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
            _upgrade_existing_report(spreadsheet, worksheet)
            return worksheet

    if start_date is None or end_date is None:
        start_date, end_date = default_report_dates(movements)
    separator = _spreadsheet_formula_separator(spreadsheet)
    _ensure_report_dimensions(worksheet)
    worksheet.clear()
    worksheet.update(
        build_report_values(
            start_date,
            end_date,
            separator=separator,
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


def _spreadsheet_formula_separator(spreadsheet: gspread.Spreadsheet) -> str:
    metadata = cast(dict[str, Any], spreadsheet.fetch_sheet_metadata())
    properties = cast(dict[str, Any], metadata.get("properties", {}))
    return formula_separator(str(properties.get("locale", "")))


def _copy_format(
    worksheet: gspread.Worksheet,
    source_range: str,
    destination_range: str,
) -> None:
    source = gspread.utils.a1_range_to_grid_range(source_range, worksheet.id)
    destination = gspread.utils.a1_range_to_grid_range(
        destination_range,
        worksheet.id,
    )
    worksheet.spreadsheet.batch_update(
        {
            "requests": [
                {
                    "copyPaste": {
                        "source": source,
                        "destination": destination,
                        "pasteType": "PASTE_FORMAT",
                        "pasteOrientation": "NORMAL",
                    }
                }
            ]
        }
    )


def _clear_format(worksheet: gspread.Worksheet, cell_range: str) -> None:
    grid_range = gspread.utils.a1_range_to_grid_range(cell_range, worksheet.id)
    worksheet.spreadsheet.batch_update(
        {
            "requests": [
                {
                    "repeatCell": {
                        "range": grid_range,
                        "fields": "userEnteredFormat",
                    }
                }
            ]
        }
    )


def _upgrade_existing_report(
    spreadsheet: gspread.Spreadsheet,
    worksheet: gspread.Worksheet,
) -> None:
    """Upgrade report formulas and layout without resetting user formatting."""
    separator = _spreadsheet_formula_separator(spreadsheet)
    current_formula = worksheet.get(
        "B27",
        value_render_option=cast(gspread.utils.ValueRenderOption, "FORMULA"),
    )[0][0]
    has_exact_dates = isinstance(current_formula, str) and "MAX($B$4" in current_formula
    has_percentages = worksheet.acell("C8").value == "Porcentaje"
    if has_exact_dates and has_percentages:
        return

    is_legacy_layout = worksheet.acell("D7").value == "Top 15 gastos"
    if not has_percentages:
        if not is_legacy_layout:
            return
        _copy_format(worksheet, "D7:F23", "E7:G23")
        _copy_format(worksheet, "B7:B13", "C7:C13")
        _copy_format(worksheet, "B15:B21", "C15:C21")
        worksheet.batch_clear(["D7:F23"])
        _clear_format(worksheet, "D7:D23")

    date_formulas = worksheet.get(
        "B4:B5",
        value_render_option=cast(gspread.utils.ValueRenderOption, "FORMULA"),
    )
    worksheet.update(
        build_report_values(
            date(2000, 1, 1),
            date(2000, 1, 31),
            separator=separator,
        ),
        range_name="A1",
        raw=False,
    )
    worksheet.update(date_formulas, range_name="B4", raw=False)
    worksheet.format(
        "C9:C13",
        {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}},
    )
    worksheet.format(
        "C17:C21",
        {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}},
    )


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
    percent_format: dict[str, Any] = {
        "numberFormat": {"type": "PERCENT", "pattern": "0.0%"}
    }
    worksheet.format("A1:K1", title_format)
    worksheet.format("A7:C8", section_format)
    worksheet.format("E7:G8", section_format)
    worksheet.format("A15:C16", section_format)
    worksheet.format(
        f"A{MONTH_TABLE_SECTION_ROW}:K{MONTH_TABLE_HEADER_ROW}",
        section_format,
    )
    worksheet.format("B4:B5", {"numberFormat": {"type": "DATE"}})
    worksheet.format("B9:B13", amount_format)
    worksheet.format("C9:C13", percent_format)
    worksheet.format(
        f"B{CATEGORY_FIRST_ROW}:B{CATEGORY_FIRST_ROW + len(EXPENSE_CATEGORIES) - 1}",
        amount_format,
    )
    worksheet.format(
        f"C{CATEGORY_FIRST_ROW}:C{CATEGORY_FIRST_ROW + len(EXPENSE_CATEGORIES) - 1}",
        percent_format,
    )
    worksheet.format(
        f"B{MONTH_TABLE_START_ROW}:K{MONTH_TABLE_END_ROW}",
        amount_format,
    )
    worksheet.format(
        f"G{TOP_EXPENSES_FIRST_ROW}:G{TOP_EXPENSES_FIRST_ROW + 14}",
        amount_format,
    )
    worksheet.freeze(rows=5)

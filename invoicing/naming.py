"""Invoice numbering, dates, and Drive folder names."""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from invoicing.models import Refuge

_WEEKDAY_PREFIXES = ("L", "M", "X", "J", "V", "S", "D")
_MONTH_NAMES = (
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
)
_WEEKDAY_LONG = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)
_MONTH_LONG = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
_INVOICE_PATTERN = re.compile(r"^factura\s+(\d+)\s*-\s*(\d{4})(?:\s|$)", re.IGNORECASE)


def slugify_alias(alias: str) -> str:
    normalized = unicodedata.normalize("NFKD", alias)
    ascii_text = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    safe = re.sub(r"[^A-Za-z0-9]+", "_", ascii_text).strip("_")
    return re.sub(r"_+", "_", safe) or "Reserva"


def date_code(starts_on: date, ends_on: date) -> str:
    start_weekday = _WEEKDAY_PREFIXES[starts_on.weekday()]
    end_weekday = _WEEKDAY_PREFIXES[ends_on.weekday()]
    start_month = _MONTH_NAMES[starts_on.month - 1]
    end_month = _MONTH_NAMES[ends_on.month - 1]

    if starts_on == ends_on:
        return f"{start_weekday}{starts_on.day}-{start_month}-{starts_on.year}"
    if starts_on.year == ends_on.year and starts_on.month == ends_on.month:
        return (
            f"{start_weekday}{starts_on.day}-{end_weekday}{ends_on.day}-"
            f"{start_month}-{starts_on.year}"
        )
    if starts_on.year == ends_on.year:
        return (
            f"{start_weekday}{starts_on.day}-{start_month}-"
            f"{end_weekday}{ends_on.day:02d}-{end_month}-{starts_on.year}"
        )
    return (
        f"{start_weekday}{starts_on.day}-{start_month}-{starts_on.year}_"
        f"{end_weekday}{ends_on.day:02d}-{end_month}-{ends_on.year}"
    )


def build_invoice_name(
    *,
    alias: str,
    starts_on: date,
    ends_on: date,
    refuge: Refuge,
    number: int,
    invoice_date: date,
) -> str:
    alias_slug = slugify_alias(alias)
    code = date_code(starts_on, ends_on)
    return (
        f"Factura {number}-{invoice_date.year} {alias_slug}_{code} {refuge.short_name}"
    )


def invoice_pdf_filename(folder_name: str) -> str:
    """Return the PDF filename for an invoice folder."""

    if folder_name.casefold().endswith(".pdf"):
        return folder_name
    return f"{folder_name}.pdf"


def preview_invoice_name(
    *,
    alias: str,
    starts_on: date,
    ends_on: date,
    refuge: Refuge,
    invoice_date: date,
    number: int | None = None,
) -> str:
    """Return a name preview without implying that a number is available."""

    return build_invoice_name(
        alias=alias,
        starts_on=starts_on,
        ends_on=ends_on,
        refuge=refuge,
        number=number or 0,
        invoice_date=invoice_date,
    ).replace("Factura 0-", "Factura N-", 1)


def invoice_quarter(invoice_date: date) -> int:
    return (invoice_date.month - 1) // 3 + 1


def year_folder_name(invoice_date: date) -> str:
    return str(invoice_date.year)


def quarter_folder_name(invoice_date: date) -> str:
    return f"GEM IVA {invoice_quarter(invoice_date)}T {invoice_date.year}"


def extract_invoice_number(name: str, year: int) -> int | None:
    match = _INVOICE_PATTERN.match(name)
    if match is None or int(match.group(2)) != year:
        return None
    return int(match.group(1))


def format_date_span(starts_on: date, ends_on: date) -> str:
    start_weekday = _WEEKDAY_LONG[starts_on.weekday()]
    start_month = _MONTH_LONG[starts_on.month - 1]
    if starts_on == ends_on:
        return (
            f"el {start_weekday} {starts_on.day} de {start_month} de {starts_on.year}"
        )

    end_weekday = _WEEKDAY_LONG[ends_on.weekday()]
    end_month = _MONTH_LONG[ends_on.month - 1]
    if starts_on.year == ends_on.year and starts_on.month == ends_on.month:
        return (
            f"el {start_weekday} {starts_on.day} y el {end_weekday} "
            f"{ends_on.day} de {start_month} de {starts_on.year}"
        )
    if starts_on.year == ends_on.year:
        return (
            f"el {start_weekday} {starts_on.day} de {start_month} y el "
            f"{end_weekday} {ends_on.day} de {end_month} de {starts_on.year}"
        )
    return (
        f"el {start_weekday} {starts_on.day} de {start_month} de {starts_on.year} "
        f"y el {end_weekday} {ends_on.day} de {end_month} de {ends_on.year}"
    )

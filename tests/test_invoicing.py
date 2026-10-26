"""Tests for invoice names, calculations, and PDF generation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Any, cast
from unittest.mock import Mock

import pytest
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from invoicing.drive import InvoiceDriveStore
from invoicing.models import (
    FreeInvoice,
    InvoiceKind,
    InvoiceValidationError,
    Refuge,
    Reservation,
    build_free_invoice,
    build_reservation,
)
from invoicing.naming import (
    build_invoice_name,
    date_code,
    extract_invoice_number,
    format_date_span,
    invoice_pdf_filename,
    invoice_quarter,
    quarter_folder_name,
)
from invoicing.pdf import build_invoice_pdf


def _reservation(*, alias: str = "Yelmo") -> Reservation:
    return build_reservation(
        official_name="Grupo Scout Yelmo",
        alias=alias,
        address="Calle Sintética 1, Madrid",
        tax_id="G12345674",
        contact="grupo@example.test",
        starts_on=date(2026, 10, 3),
        ends_on=date(2026, 10, 4),
        refuge=Refuge.LA_LASTRA,
        participants=5,
        rate_per_participant=Decimal("7.00"),
        vat_rate=Decimal("10"),
    )


def _free_invoice(
    *,
    custom_name: str = "Cuota anual",
    invoice_date: date = date(2026, 10, 26),
) -> FreeInvoice:
    return build_free_invoice(
        official_name="Entidad Libre Sintética",
        custom_name=custom_name,
        address="Avenida de Prueba 2, Madrid",
        tax_id="G12345674",
        contact="libre@example.test",
        description="Cuota anual de colaboración.\nSegunda línea del concepto.",
        invoice_date=invoice_date,
        total_including_vat=Decimal("121.00"),
        vat_rate=Decimal("21"),
    )


def test_night_and_vat_calculation() -> None:
    reservation = _reservation()

    assert reservation.nights == 1
    assert reservation.total_including_vat == Decimal("35.00")
    assert reservation.taxable_base == Decimal("31.82")
    assert reservation.vat_amount == Decimal("3.18")


def test_same_day_reservation_is_billed_as_one_night() -> None:
    reservation = build_reservation(
        official_name="Entidad Sintética",
        alias="Entidad",
        address="Calle Sintética 2",
        tax_id="G12345674",
        contact="contacto@example.test",
        starts_on=date(2026, 10, 3),
        ends_on=date(2026, 10, 3),
        refuge=Refuge.EL_MORTERO,
        participants=1,
        rate_per_participant=Decimal("10"),
        vat_rate=Decimal("10"),
    )

    assert reservation.nights == 1
    assert reservation.total_including_vat == Decimal("10.00")


def test_same_month_date_code_and_invoice_name() -> None:
    assert date_code(date(2026, 10, 3), date(2026, 10, 4)) == "S3-D4-oct-2026"
    reservation = _reservation()
    assert (
        build_invoice_name(
            invoice=reservation,
            number=25,
            invoice_date=date(2026, 10, 8),
        )
        == "Factura 25-2026 Yelmo_S3-D4-oct-2026 Lastra"
    )
    assert (
        invoice_pdf_filename("Factura 25-2026 Yelmo_S3-D4-oct-2026 Lastra")
        == "Factura 25-2026 Yelmo_S3-D4-oct-2026 Lastra.pdf"
    )


def test_cross_month_date_code_matches_agreed_example() -> None:
    assert date_code(date(2026, 10, 30), date(2026, 11, 1)) == "V30-oct-D01-nov-2026"


def test_alias_is_safe_for_drive_files() -> None:
    reservation = _reservation(alias="  Grupo Ágil / Norte  ")
    name = build_invoice_name(
        invoice=reservation,
        number=1,
        invoice_date=date(2026, 10, 8),
    )

    assert name == "Factura 1-2026 Grupo_Agil_Norte_S3-D4-oct-2026 Lastra"


def test_free_invoice_uses_custom_name_and_configurable_amount() -> None:
    invoice = _free_invoice()

    assert invoice.kind is InvoiceKind.LIBRE
    assert invoice.description == (
        "Cuota anual de colaboración.\nSegunda línea del concepto."
    )
    assert invoice.taxable_base == Decimal("100.00")
    assert invoice.vat_amount == Decimal("21.00")
    assert invoice.total_including_vat == Decimal("121.00")
    assert (
        build_invoice_name(
            invoice=invoice,
            number=27,
            invoice_date=invoice.invoice_date,
        )
        == "Factura 27-2026 Cuota_anual"
    )


def test_quarter_uses_invoice_date() -> None:
    assert invoice_quarter(date(2027, 1, 1)) == 1
    assert quarter_folder_name(date(2027, 4, 1)) == "GEM IVA 2T 2027"


def test_number_parser_rejects_another_year() -> None:
    assert extract_invoice_number("Factura 26-2026 Ejemplo", 2026) == 26
    assert extract_invoice_number("Factura 26-2025 Ejemplo", 2026) is None


def test_next_number_uses_one_drive_search() -> None:
    service = Mock()
    service.files.return_value.list.return_value.execute.return_value = {
        "files": [
            {"name": "Factura 26-2026 Ejemplo"},
            {"name": "Factura 4-2025 Ejemplo"},
        ]
    }
    store = InvoiceDriveStore(service)

    assert store.next_invoice_number(date(2026, 10, 26)) == 27
    service.files.return_value.list.assert_called_once()


def test_duplicate_fingerprint_ignores_invoice_date_and_whitespace() -> None:
    first = _reservation()
    second = _reservation(alias=" Yelmo ")

    assert first.invoice_hash == second.invoice_hash


def test_free_invoice_fingerprint_includes_invoice_date() -> None:
    first = _free_invoice()
    second = _free_invoice(custom_name=" Cuota   anual ")
    another_date = _free_invoice(invoice_date=date(2026, 10, 27))

    assert first.invoice_hash == second.invoice_hash
    assert first.invoice_hash != another_date.invoice_hash


def test_invalid_cif_is_rejected() -> None:
    with pytest.raises(InvoiceValidationError):
        build_reservation(
            official_name="Entidad Sintética",
            alias="Entidad",
            address="Calle Sintética 2",
            tax_id="not-a-cif",
            contact="contacto@example.test",
            starts_on=date(2026, 10, 3),
            ends_on=date(2026, 10, 3),
            refuge=Refuge.EL_MORTERO,
            participants=1,
            rate_per_participant=Decimal("10"),
            vat_rate=Decimal("10"),
        )


def test_date_span() -> None:
    assert (
        format_date_span(date(2026, 10, 3), date(2026, 10, 4))
        == "el sábado 3 y el domingo 4 de octubre de 2026"
    )


def test_pdf_contains_invoice_data_and_images() -> None:
    reservation = _reservation(alias="Grupo de prueba")
    pdf_bytes = build_invoice_pdf(
        reservation,
        number=27,
        invoice_date=date(2026, 10, 26),
    )

    assert pdf_bytes.startswith(b"%PDF")
    reader = PdfReader(BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "FACTURA" in text
    assert "27-2026" in text
    assert "Grupo Scout Yelmo" in text
    assert "refugio de La Lastra" in text
    assert "35,00" in text
    assert "€" in text
    resources = cast(dict[str, Any], reader.pages[0]["/Resources"])
    assert len(resources["/XObject"]) >= 2


def test_free_invoice_pdf_uses_standard_images_and_custom_description() -> None:
    invoice = _free_invoice()
    pdf_bytes = build_invoice_pdf(
        invoice,
        number=27,
        invoice_date=invoice.invoice_date,
    )

    reader = PdfReader(BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Entidad Libre Sintética" in text
    assert "Cuota anual de colaboración." in text
    assert "Segunda línea del concepto." in text
    assert "Cuota anual de colaboración.\nSegunda línea del concepto." in text
    assert "100,00" in text
    assert "21,00" in text
    assert "€" in text
    assert "refugio de" not in text
    resources = cast(dict[str, Any], reader.pages[0]["/Resources"])
    assert len(resources["/XObject"]) >= 2


def test_invoice_app_offers_reservation_and_free_types() -> None:
    app = AppTest.from_file("invoice_app.py")
    app.run(timeout=20)

    assert not app.exception
    type_selector = next(
        item for item in app.selectbox if item.label == "Tipo de factura *"
    )
    assert type_selector.options == [
        InvoiceKind.RESERVA.value,
        InvoiceKind.LIBRE.value,
    ]
    assert app.button[0].disabled

    type_selector.set_value(InvoiceKind.LIBRE.value)
    app.run(timeout=20)
    assert not app.exception
    assert [item.label for item in app.text_area] == [
        "Domicilio *",
        "Descripción o concepto *",
    ]
    assert [item.label for item in app.date_input] == ["Fecha de factura *"]
    assert [item.label for item in app.number_input] == [
        "Importe total (IVA incluido) *",
        "Tipo de IVA (%) *",
    ]

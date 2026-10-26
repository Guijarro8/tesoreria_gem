"""Fill the established GEM invoice template with dynamic values."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from invoicing.models import FreeInvoice, InvoiceDocument, Reservation
from invoicing.naming import format_date_span

_ASSET_DIRECTORY = Path(__file__).resolve().parent.parent / "assets"
_TEMPLATE_PATH = _ASSET_DIRECTORY / "invoice_template.pdf"
_PAGE_WIDTH, _PAGE_HEIGHT = landscape(A4)
_REGULAR_FONT = "Helvetica"
_BOLD_FONT = "Helvetica-Bold"
_BLACK = (0, 0, 0)


def _amount(value: Decimal) -> str:
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "\0").replace(".", ",").replace("\0", ".")


def _rate(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(value.to_integral_value())
    return _amount(value)


def _fit_text(text: str, *, font_name: str, font_size: float, width: float) -> str:
    if stringWidth(text, font_name, font_size) <= width:
        return text
    suffix = "..."
    while (
        text
        and stringWidth(
            text + suffix,
            font_name,
            font_size,
        )
        > width
    ):
        text = text[:-1]
    return text + suffix


def _concept_text(invoice: InvoiceDocument) -> str:
    if isinstance(invoice, Reservation):
        participant_word = "persona" if invoice.participants == 1 else "personas"
        activity_dates = format_date_span(invoice.starts_on, invoice.ends_on)
        return (
            "Asistencia logística para actividad de educación ambiental en el "
            f"refugio de {invoice.refuge.display_name} {activity_dates}, con la "
            f"participación de {invoice.participants} {participant_word}. "
            "El precio incluye seguro de responsabilidad civil, alojamiento, "
            "consumo de leña, gas, electricidad y agua, utilización de todos los "
            "enseres del refugio e impuestos."
        )
    if isinstance(invoice, FreeInvoice):
        return invoice.description
    raise TypeError("Unsupported invoice type")


def _draw_concept(
    pdf: canvas.Canvas,
    invoice: InvoiceDocument,
) -> None:
    text = escape(_concept_text(invoice)).replace("\n", "<br/>")
    x = 121.94
    top = _PAGE_HEIGHT - 301.81
    width = 589.74
    max_height = 84.0
    sizes = (
        (12.0, 14.76),
        (11.5, 14.2),
        (11.0, 13.6),
        (10.5, 13.0),
        (10.0, 12.4),
        (9.5, 11.8),
        (9.0, 11.2),
        (8.5, 10.6),
        (8.0, 10.0),
        (7.5, 9.4),
    )
    paragraph: Paragraph | None = None
    height = 0.0
    for font_size, leading in sizes:
        style = ParagraphStyle(
            name=f"InvoiceConcept-{font_size}",
            fontName=_REGULAR_FONT,
            fontSize=font_size,
            leading=leading,
            textColor=_BLACK,
        )
        paragraph = Paragraph(text, style)
        _, wrapped_height = paragraph.wrap(width, max_height + 1)
        height = float(wrapped_height)
        if height <= max_height:
            break
    if paragraph is None:
        return
    paragraph.drawOn(pdf, x, top - height)


def _draw_amount_table(
    pdf: canvas.Canvas,
    invoice: InvoiceDocument,
) -> None:
    value_right = 563.39
    label_x = 567.79
    row_baselines = (139.22, 124.46, 109.70)
    horizontal_lines = (150.86, 136.10, 121.34, 106.58)
    vertical_top = 150.80
    vertical_bottom = 105.68

    pdf.setStrokeColorRGB(*_BLACK)
    pdf.setLineWidth(0.96)
    for y in horizontal_lines:
        pdf.line(489.43, y, 566.11, y)
    pdf.line(488.53, vertical_bottom, 488.53, vertical_top)
    pdf.line(565.21, vertical_bottom, 565.21, vertical_top)

    pdf.setFillColorRGB(*_BLACK)
    pdf.setFont(_BOLD_FONT, 12)
    pdf.drawRightString(value_right, row_baselines[0], _amount(invoice.taxable_base))
    pdf.drawRightString(value_right, row_baselines[1], _amount(invoice.vat_amount))
    pdf.drawRightString(
        value_right,
        row_baselines[2],
        _amount(invoice.total_including_vat),
    )
    pdf.drawString(label_x, row_baselines[0], "Base imponible")
    pdf.drawString(label_x, row_baselines[1], f"{_rate(invoice.vat_rate)} % IVA")
    pdf.drawString(label_x, row_baselines[2], "TOTAL")


def _build_overlay(
    invoice: InvoiceDocument,
    *,
    number: int,
    invoice_date: date,
) -> bytes:
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=(_PAGE_WIDTH, _PAGE_HEIGHT))
    pdf.setFillColorRGB(*_BLACK)

    pdf.setFont(_BOLD_FONT, 18)
    invoice_code = _fit_text(
        f"{number}-{invoice_date.year}",
        font_name=_BOLD_FONT,
        font_size=18,
        width=220,
    )
    pdf.drawString(268.70, _PAGE_HEIGHT - 182.21, invoice_code)
    pdf.drawString(
        568.63,
        _PAGE_HEIGHT - 182.21,
        invoice_date.strftime("%d/%m/%Y"),
    )

    pdf.setFont(_REGULAR_FONT, 12)
    client_values = (
        (214.13, invoice.official_name),
        (228.89, invoice.address),
        (242.69, invoice.tax_id),
        (257.93, invoice.contact),
    )
    for origin_y, value in client_values:
        pdf.drawString(
            267.86,
            _PAGE_HEIGHT - origin_y,
            _fit_text(
                value,
                font_name=_REGULAR_FONT,
                font_size=12,
                width=455,
            ),
        )

    _draw_concept(pdf, invoice)

    pdf.setFont(_BOLD_FONT, 12)
    pdf.drawRightString(
        563.39,
        _PAGE_HEIGHT - 396.94,
        _amount(invoice.total_including_vat),
    )
    pdf.drawString(567.79, _PAGE_HEIGHT - 396.94, "€")
    _draw_amount_table(pdf, invoice)

    # The historical template's top border crosses the dynamic invoice and date
    # fields. Redrawing it keeps the border continuous after those fields are
    # cleared from the reusable background.
    pdf.setStrokeColorRGB(*_BLACK)
    pdf.setLineWidth(0.96)
    pdf.line(102.54, _PAGE_HEIGHT - 187.55, 726.16, _PAGE_HEIGHT - 187.55)

    pdf.showPage()
    pdf.save()
    return output.getvalue()


def build_invoice_pdf(
    invoice: InvoiceDocument,
    *,
    number: int,
    invoice_date: date,
) -> bytes:
    """Overlay invoice data onto a template derived from the historical PDF."""

    overlay = PdfReader(
        BytesIO(
            _build_overlay(
                invoice,
                number=number,
                invoice_date=invoice_date,
            )
        )
    )
    writer = PdfWriter(clone_from=str(_TEMPLATE_PATH))
    writer.pages[0].merge_page(overlay.pages[0])
    writer.add_metadata(
        {
            "/Title": f"Factura {number}-{invoice_date.year}",
            "/Author": "GEM",
            "/Subject": "Factura",
        }
    )
    output = BytesIO()
    writer.write(output)
    return output.getvalue()

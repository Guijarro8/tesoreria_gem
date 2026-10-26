"""Render a reservation invoice as a fixed-layout PDF."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from invoicing.models import Reservation
from invoicing.naming import format_date_span

_ASSET_DIRECTORY = Path(__file__).resolve().parent.parent / "assets"
_GEM_RED = colors.HexColor("#C62839")
_DARK = colors.HexColor("#292929")
_MUTED = colors.HexColor("#5C5C5C")
_BORDER = colors.HexColor("#D9D9D9")
_LIGHT_GREY = colors.HexColor("#F5F5F5")

_ASSOCIATION_TITLE = "Guías de Espeleología y Montaña GEM"
_ASSOCIATION_DESCRIPTION = (
    "Organización No Gubernamental dedicada a la investigación y conservación "
    "de la naturaleza y el patrimonio cultural, la cooperación para el desarrollo "
    "y la educación ambiental. El importe facturado se dedica íntegramente al "
    "sostenimiento de proyectos de interés social y ambiental y los refugios de "
    "las casillas de El Mortero y La Lastra."
)
_ASSOCIATION_FISCAL = (
    "CIF: G82150103 · Domicilio fiscal: Casilla del Mortero · "
    "28189 Torremocha de Jarama"
)
_ASSOCIATION_CONTACT = (
    "Dirección para comunicaciones: Apartado de correos nº 22 · 28180 Torrelaguna"
    "<br/>Teléfono / WhatsApp: 656408790 / 641471580"
)
_PAYMENT_DETAILS = (
    "Número de cuenta para ingresar el importe facturado: "
    "ES60 0081 0309 72 0001861591 · Titular: GEM"
)
_PAYMENT_NOTE = (
    "Por favor, para facilitar el trabajo a nuestro tesorero indica el número de "
    "factura en el concepto del ingreso o transferencia y envíanos un justificante "
    "de pago."
)
_PRICE_DESCRIPTION = (
    "El precio incluye seguro de responsabilidad civil, alojamiento, consumo de "
    "leña, gas, electricidad y agua, utilización de todos los enseres del refugio "
    "e impuestos."
)


def _money(value: Decimal) -> str:
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "\0").replace(".", ",").replace("\0", ".") + " €"


def _number(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(value.to_integral_value())
    return f"{value:,.2f}".replace(",", "\0").replace(".", ",").replace("\0", ".")


def _paragraph_style(
    *,
    font_name: str = "Helvetica",
    font_size: float,
    leading: float,
    color: colors.Color = _DARK,
) -> ParagraphStyle:
    return ParagraphStyle(
        name=f"Invoice-{font_name}-{font_size}-{leading}",
        fontName=font_name,
        fontSize=font_size,
        leading=leading,
        textColor=color,
    )


def _draw_paragraph(
    pdf: canvas.Canvas,
    text: str,
    *,
    x: float,
    y: float,
    width: float,
    style: ParagraphStyle,
) -> float:
    paragraph = Paragraph(text, style)
    _, height = paragraph.wrap(width, 200 * mm)
    paragraph.drawOn(pdf, x, y - height)
    return y - float(height)


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


def build_invoice_pdf(
    reservation: Reservation,
    *,
    number: int,
    invoice_date: date,
) -> bytes:
    """Build the invoice in memory so Drive is untouched if rendering fails."""

    output = BytesIO()
    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(output, pagesize=(page_width, page_height))
    pdf.setTitle(f"Factura {number}-{invoice_date.year}")
    pdf.setAuthor("GEM")
    pdf.setSubject("Factura de reserva")

    small = _paragraph_style(font_size=7.4, leading=9.2)
    muted = _paragraph_style(font_size=7.4, leading=9.2, color=_MUTED)
    body = _paragraph_style(font_size=9.2, leading=12.4)

    left = 15 * mm
    right = page_width - 15 * mm
    logo_width = 18 * mm
    logo_height = 19 * mm
    pdf.drawImage(
        str(_ASSET_DIRECTORY / "invoice_logo.jpg"),
        left,
        page_height - 25 * mm,
        width=logo_width,
        height=logo_height,
        preserveAspectRatio=True,
        anchor="sw",
        mask="auto",
    )
    text_x = left + logo_width + 7 * mm
    text_width = right - text_x
    pdf.setFillColor(_DARK)
    pdf.setFont("Helvetica-Bold", 14.5)
    pdf.drawString(text_x, page_height - 13 * mm, _ASSOCIATION_TITLE)
    cursor = _draw_paragraph(
        pdf,
        _ASSOCIATION_DESCRIPTION,
        x=text_x,
        y=page_height - 17 * mm,
        width=text_width,
        style=small,
    )
    cursor = _draw_paragraph(
        pdf,
        _ASSOCIATION_FISCAL,
        x=text_x,
        y=cursor - 2 * mm,
        width=text_width,
        style=muted,
    )
    cursor = _draw_paragraph(
        pdf,
        _ASSOCIATION_CONTACT,
        x=text_x,
        y=cursor - 0.5 * mm,
        width=text_width,
        style=muted,
    )
    divider_y = min(cursor - 3 * mm, page_height - 36 * mm)
    pdf.setStrokeColor(_BORDER)
    pdf.line(left, divider_y, right, divider_y)

    title_y = divider_y - 9 * mm
    pdf.setFillColor(_GEM_RED)
    pdf.setFont("Helvetica-Bold", 19)
    pdf.drawString(left, title_y, "FACTURA")
    pdf.setFillColor(_DARK)
    pdf.setFont("Helvetica-Bold", 11.5)
    pdf.drawString(left + 38 * mm, title_y, f"{number}-{invoice_date.year}")
    pdf.setFont("Helvetica", 9.2)
    pdf.drawRightString(
        right,
        title_y,
        f"Fecha: {invoice_date:%d/%m/%Y}",
    )

    client_top = title_y - 9 * mm
    label_width = 20 * mm
    value_x = left + label_width
    pdf.setFillColor(_GEM_RED)
    pdf.setFont("Helvetica-Bold", 9.2)
    pdf.drawString(left, client_top, "Cliente:")
    pdf.setFillColor(_DARK)
    pdf.setFont("Helvetica-Bold", 9.2)
    official_name = _fit_text(
        reservation.official_name,
        font_name="Helvetica-Bold",
        font_size=9.2,
        width=right - value_x,
    )
    pdf.drawString(value_x, client_top, official_name)
    rows = (
        ("Domicilio:", reservation.address),
        ("CIF:", reservation.tax_id),
        ("Contacto:", reservation.contact),
    )
    cursor = client_top
    for row_label, row_value in rows:
        cursor -= 5.7 * mm
        pdf.setFillColor(_MUTED)
        pdf.setFont("Helvetica-Bold", 8.6)
        pdf.drawString(left, cursor, row_label)
        pdf.setFillColor(_DARK)
        pdf.setFont("Helvetica", 8.8)
        max_width = right - value_x
        text = _fit_text(
            row_value,
            font_name="Helvetica",
            font_size=8.8,
            width=max_width,
        )
        pdf.drawString(value_x, cursor, text)

    concept_top = cursor - 8 * mm
    pdf.setFillColor(_GEM_RED)
    pdf.setFont("Helvetica-Bold", 9.2)
    pdf.drawString(left, concept_top, "Por el siguiente concepto:")
    concept_y = concept_top - 4 * mm
    concept_height = 28 * mm
    pdf.setFillColor(_LIGHT_GREY)
    pdf.setStrokeColor(_BORDER)
    pdf.roundRect(
        left,
        concept_y - concept_height,
        right - left,
        concept_height,
        2 * mm,
        fill=1,
        stroke=1,
    )

    participant_word = "persona" if reservation.participants == 1 else "personas"
    activity_dates = format_date_span(reservation.starts_on, reservation.ends_on)
    concept = (
        f"Asistencia logística para actividad de educación ambiental en el refugio "
        f"de {reservation.refuge.display_name} "
        f"{activity_dates}, con la participación de {reservation.participants} "
        f"{participant_word}. {_PRICE_DESCRIPTION}"
    )
    concept_width = right - left - 9 * mm
    concept_cursor = _draw_paragraph(
        pdf,
        escape(concept),
        x=left + 4 * mm,
        y=concept_y - 3 * mm,
        width=concept_width,
        style=body,
    )
    calculation = (
        f"{reservation.nights} noche(s) x {reservation.participants} "
        f"{participant_word} x {_money(reservation.rate_per_participant)}"
    )
    pdf.setFillColor(_MUTED)
    pdf.setFont("Helvetica", 7.6)
    pdf.drawString(
        left + 4 * mm,
        max(concept_y - concept_height + 2.5 * mm, concept_cursor - 1 * mm),
        calculation,
    )

    table_width = 72 * mm
    table_x = right - table_width
    table_bottom = concept_y - concept_height - 5 * mm
    row_height = 7 * mm
    rows = (
        ("Base imponible", _money(reservation.taxable_base)),
        (f"{_number(reservation.vat_rate)} % IVA", _money(reservation.vat_amount)),
    )
    pdf.setStrokeColor(_BORDER)
    for index, (row_label, row_value) in enumerate(rows):
        row_y = table_bottom - (index + 1) * row_height
        pdf.setFillColor(colors.white)
        pdf.rect(table_x, row_y, table_width, row_height, fill=1, stroke=1)
        pdf.setFillColor(_DARK)
        pdf.setFont("Helvetica", 8.8)
        pdf.drawString(table_x + 2.5 * mm, row_y + 2.2 * mm, row_label)
        pdf.drawRightString(
            table_x + table_width - 2.5 * mm,
            row_y + 2.2 * mm,
            row_value,
        )

    total_y = table_bottom - 3 * row_height
    pdf.setFillColor(_GEM_RED)
    pdf.roundRect(
        table_x,
        total_y,
        table_width,
        row_height,
        1.2 * mm,
        fill=1,
        stroke=0,
    )
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(table_x + 2.5 * mm, total_y + 2.2 * mm, "TOTAL")
    pdf.drawRightString(
        table_x + table_width - 2.5 * mm,
        total_y + 2.2 * mm,
        _money(reservation.total_including_vat),
    )

    signature_width = 31 * mm
    signature_height = 24 * mm
    pdf.drawImage(
        str(_ASSET_DIRECTORY / "invoice_signature.jpg"),
        table_x - signature_width - 15 * mm,
        max(total_y - signature_height + 2 * mm, 28 * mm),
        width=signature_width,
        height=signature_height,
        preserveAspectRatio=True,
        anchor="sw",
        mask="auto",
    )

    payment_y = 24 * mm
    pdf.setStrokeColor(_BORDER)
    pdf.line(left, payment_y + 7 * mm, right, payment_y + 7 * mm)
    _draw_paragraph(
        pdf,
        f"<b>{escape(_PAYMENT_DETAILS)}</b>",
        x=left,
        y=payment_y + 5 * mm,
        width=right - left,
        style=small,
    )
    _draw_paragraph(
        pdf,
        escape(_PAYMENT_NOTE),
        x=left,
        y=payment_y + 0.5 * mm,
        width=right - left,
        style=muted,
    )
    pdf.showPage()
    pdf.save()
    return output.getvalue()

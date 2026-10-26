"""Public Streamlit form for creating standard GEM invoices."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast
from zoneinfo import ZoneInfo

import streamlit as st

from invoicing import (
    FreeInvoice,
    InvoiceCreation,
    InvoiceDocument,
    InvoiceDriveStore,
    InvoiceKind,
    InvoiceValidationError,
    Refuge,
    Reservation,
    build_free_invoice,
    build_invoice_name,
    preview_invoice_name,
)
from invoicing.models import build_reservation

_MADRID = ZoneInfo("Europe/Madrid")


def _read_secret(name: str) -> str:
    if name not in st.secrets:
        raise ValueError(f"Missing secret: {name}")
    return str(st.secrets[name])


@st.cache_resource
def _load_invoice_store() -> InvoiceDriveStore:
    credentials = cast(
        dict[str, Any],
        json.loads(_read_secret("gcp_credentials")),
    )
    root_folder_id = str(st.secrets.get("invoice_root_folder_id", "")).strip()
    if root_folder_id:
        return InvoiceDriveStore.from_service_account(
            credentials,
            root_folder_id=root_folder_id,
        )
    return InvoiceDriveStore.from_service_account(credentials)


def _today() -> date:
    return datetime.now(_MADRID).date()


def _show_created_invoice(
    result: InvoiceCreation,
    *,
    invoice_date: date,
) -> None:
    if result.already_exists:
        st.warning(
            f"Ya existe una factura con estos datos: {result.number}-"
            f"{invoice_date.year}."
        )
    else:
        st.success(f"Factura {result.number}-{invoice_date.year} creada correctamente.")
    st.link_button(
        "Abrir carpeta de la factura",
        result.folder_url,
        use_container_width=True,
    )


def _next_number_for_preview(
    *,
    invoice_date: date,
) -> int | None:
    cache_key = f"invoice_preview_number_{invoice_date.isoformat()}"
    try:
        store = _load_invoice_store()
        cached = cast(int | None, st.session_state.get(cache_key))
        if cached is not None:
            return cached
        number = store.next_invoice_number(invoice_date)
        st.session_state[cache_key] = number
        return number
    except Exception:
        return None


def main() -> None:
    """Render the invoice form."""

    st.set_page_config(
        page_title="Nueva factura · GEM",
        page_icon="🧾",
        layout="wide",
    )
    st.title("Nueva factura")
    st.caption("Los enlaces a las facturas requieren permisos de socio GEM.")

    invoice_kind = st.selectbox(
        "Tipo de factura *",
        options=[kind.value for kind in InvoiceKind],
    )
    is_reservation = invoice_kind == InvoiceKind.RESERVA.value

    default_invoice_date = _today()
    left, right = st.columns(2)
    with left:
        official_name = st.text_input(
            "Razón social o nombre oficial *",
            max_chars=180,
            placeholder="Nombre que figurará en la factura",
        )
        address = st.text_area(
            "Domicilio *",
            max_chars=300,
            height=90,
        )
        contact = st.text_input(
            "Contacto *",
            max_chars=180,
        )
    with right:
        if is_reservation:
            alias = st.text_input(
                "Alias *",
                max_chars=60,
                placeholder="Nombre corto para carpeta y PDF",
            )
        else:
            custom_name = st.text_input(
                "Nombre de carpeta y PDF *",
                max_chars=90,
                placeholder="Se añadirá después del número de factura",
            )
        tax_id = st.text_input(
            "CIF *",
            max_chars=20,
        )
        if is_reservation:
            refuge = st.selectbox(
                "Refugio *",
                options=list(Refuge),
                format_func=lambda item: item.value,
            )
        else:
            default_invoice_date = st.date_input(
                "Fecha de factura *",
                value=default_invoice_date,
            )

    if is_reservation:
        date_left, date_right, people_column, rate_column = st.columns(4)
        with date_left:
            starts_on = st.date_input("Fecha de inicio *", value=default_invoice_date)
        with date_right:
            ends_on = st.date_input("Fecha de fin *", value=default_invoice_date)
        with people_column:
            participants = st.number_input(
                "Participantes *",
                min_value=1,
                max_value=10_000,
                value=1,
                step=1,
            )
        with rate_column:
            rate_per_participant = st.number_input(
                "Cuota por participante *",
                min_value=0.01,
                max_value=100_000.0,
                value=7.00,
                step=0.5,
                format="%.2f",
            )
        vat_rate = st.number_input(
            "Tipo de IVA (%) *",
            min_value=0.0,
            max_value=100.0,
            value=10.0,
            step=0.5,
            format="%.2f",
        )
        invoice_date = default_invoice_date
    else:
        description = st.text_area(
            "Descripción o concepto *",
            max_chars=1_000,
            height=150,
            placeholder="Texto que aparecerá en el recuadro de concepto",
        )
        amount_column, vat_column = st.columns(2)
        with amount_column:
            total_including_vat = st.number_input(
                "Importe total (IVA incluido) *",
                min_value=0.0,
                max_value=10_000_000.0,
                value=0.0,
                step=1.0,
                format="%.2f",
            )
        with vat_column:
            vat_rate = st.number_input(
                "Tipo de IVA (%) *",
                min_value=0.0,
                max_value=100.0,
                value=10.0,
                step=0.5,
                format="%.2f",
            )
        invoice_date = default_invoice_date

    document: InvoiceDocument | None = None
    validation_error: str | None = None
    try:
        if is_reservation:
            document = build_reservation(
                official_name=official_name,
                alias=alias,
                address=address,
                tax_id=tax_id,
                contact=contact,
                starts_on=starts_on,
                ends_on=ends_on,
                refuge=refuge,
                participants=int(participants),
                rate_per_participant=Decimal(str(rate_per_participant)),
                vat_rate=Decimal(str(vat_rate)),
            )
        else:
            document = build_free_invoice(
                official_name=official_name,
                custom_name=custom_name,
                address=address,
                tax_id=tax_id,
                contact=contact,
                description=description,
                invoice_date=invoice_date,
                total_including_vat=Decimal(str(total_including_vat)),
                vat_rate=Decimal(str(vat_rate)),
            )
    except InvoiceValidationError as error:
        validation_error = str(error)

    preview_column, button_column = st.columns(
        [4, 1.35],
        vertical_alignment="bottom",
    )
    preview: str | None = None
    if document is not None:
        preview = preview_invoice_name(
            invoice=document,
            invoice_date=invoice_date,
            number=_next_number_for_preview(invoice_date=invoice_date),
        )
    with preview_column:
        st.caption("Carpeta que se creará")
        if preview is None:
            st.info("Completa los campos obligatorios para ver la vista previa.")
        else:
            st.code(preview, language=None)
            if isinstance(document, Reservation):
                st.caption(
                    f"{document.nights} noche(s) x "
                    f"{document.participants} participante(s) x "
                    f"{document.rate_per_participant:.2f} € · IVA incluido: "
                    f"{document.total_including_vat:.2f} €"
                )
            elif isinstance(document, FreeInvoice):
                st.caption(
                    f"Importe total con IVA incluido: "
                    f"{document.total_including_vat:.2f} €"
                )
    with button_column:
        create_clicked = st.button(
            "Crear factura",
            type="primary",
            use_container_width=True,
            disabled=document is None,
        )

    common_fields_filled = all(
        value.strip() for value in (official_name, address, tax_id, contact)
    )
    type_fields_filled = (
        bool(alias.strip())
        if is_reservation
        else bool(custom_name.strip() and description.strip())
    )
    if validation_error is not None and common_fields_filled and type_fields_filled:
        st.error(validation_error)

    if not create_clicked or document is None:
        return

    try:
        result = _load_invoice_store().create_invoice(
            document,
            invoice_date=invoice_date,
        )
    except InvoiceValidationError as error:
        st.error(str(error))
        return
    except Exception:
        st.error(
            "No se pudo crear la factura. No se ha mostrado ningún dato personal. "
            "Revisa la conexión con Drive e inténtalo de nuevo."
        )
        return

    st.session_state[f"invoice_preview_number_{invoice_date.isoformat()}"] = (
        result.number + 1
    )
    _show_created_invoice(result, invoice_date=invoice_date)
    st.code(
        build_invoice_name(
            invoice=document,
            number=result.number,
            invoice_date=invoice_date,
        ),
        language=None,
    )


if __name__ == "__main__":
    main()

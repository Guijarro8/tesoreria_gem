"""Public Streamlit form for creating GEM reservation invoices."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast
from zoneinfo import ZoneInfo

import streamlit as st

from invoicing import (
    InvoiceCreation,
    InvoiceDriveStore,
    InvoiceValidationError,
    Refuge,
    Reservation,
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


def _validated_reservation(
    *,
    official_name: str,
    alias: str,
    address: str,
    tax_id: str,
    contact: str,
    starts_on: date,
    ends_on: date,
    refuge: Refuge,
    participants: int,
    rate_per_participant: float,
    vat_rate: float,
) -> Reservation:
    return build_reservation(
        official_name=official_name,
        alias=alias,
        address=address,
        tax_id=tax_id,
        contact=contact,
        starts_on=starts_on,
        ends_on=ends_on,
        refuge=refuge,
        participants=participants,
        rate_per_participant=Decimal(str(rate_per_participant)),
        vat_rate=Decimal(str(vat_rate)),
    )


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


def main() -> None:
    """Render the reservation invoice form."""

    st.set_page_config(
        page_title="Nueva factura de reserva · GEM",
        page_icon="🧾",
        layout="wide",
    )
    st.title("Nueva factura de reserva")
    st.caption("Los enlaces a las facturas requieren permisos de socio GEM.")

    left, right = st.columns(2)
    with left:
        official_name = st.text_input(
            "Nombre oficial *",
            max_chars=180,
            placeholder="Grupo o entidad que figura en la factura",
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
        alias = st.text_input(
            "Alias *",
            max_chars=60,
            placeholder="Nombre corto para carpeta y archivo",
        )
        tax_id = st.text_input(
            "CIF *",
            max_chars=20,
        )
        refuge = st.selectbox(
            "Refugio *",
            options=list(Refuge),
            format_func=lambda item: item.value,
        )

    date_left, date_right, people_column, rate_column = st.columns(4)
    with date_left:
        starts_on = st.date_input("Fecha de inicio *", value=_today())
    with date_right:
        ends_on = st.date_input("Fecha de fin *", value=_today())
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

    invoice_date = _today()
    reservation: Reservation | None = None
    validation_error: str | None = None
    try:
        reservation = _validated_reservation(
            official_name=official_name,
            alias=alias,
            address=address,
            tax_id=tax_id,
            contact=contact,
            starts_on=starts_on,
            ends_on=ends_on,
            refuge=refuge,
            participants=int(participants),
            rate_per_participant=float(rate_per_participant),
            vat_rate=float(vat_rate),
        )
    except InvoiceValidationError as error:
        validation_error = str(error)

    preview_column, button_column = st.columns(
        [4, 1.35],
        vertical_alignment="bottom",
    )
    preview = None
    if reservation is not None:
        preview_number: int | None = None
        try:
            preview_store = _load_invoice_store()
            cache_key = f"invoice_preview_number_{invoice_date.isoformat()}"
            preview_number = cast(
                int | None,
                st.session_state.get(cache_key),
            )
            if preview_number is None:
                preview_number = preview_store.next_invoice_number(invoice_date)
                st.session_state[cache_key] = preview_number
        except Exception:
            preview_number = None
        preview = preview_invoice_name(
            alias=reservation.alias,
            starts_on=reservation.starts_on,
            ends_on=reservation.ends_on,
            refuge=reservation.refuge,
            invoice_date=invoice_date,
            number=preview_number,
        )
    with preview_column:
        st.caption("Carpeta que se creará")
        if preview is None:
            st.info("Completa los campos obligatorios para ver la vista previa.")
        else:
            valid_reservation = cast(Reservation, reservation)
            st.code(preview, language=None)
            st.caption(
                f"{valid_reservation.nights} noche(s) x "
                f"{valid_reservation.participants} participante(s) x "
                f"{valid_reservation.rate_per_participant:.2f} € · IVA incluido: "
                f"{valid_reservation.total_including_vat:.2f} €"
            )
    with button_column:
        create_clicked = st.button(
            "Crear factura",
            type="primary",
            use_container_width=True,
            disabled=reservation is None,
        )

    if validation_error is not None and all(
        value.strip() for value in (official_name, alias, address, tax_id, contact)
    ):
        st.error(validation_error)

    if not create_clicked or reservation is None:
        return

    try:
        store = _load_invoice_store()
        result = store.create_invoice(reservation, invoice_date=invoice_date)
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
            alias=reservation.alias,
            starts_on=reservation.starts_on,
            ends_on=reservation.ends_on,
            refuge=reservation.refuge,
            number=result.number,
            invoice_date=invoice_date,
        ),
        language=None,
    )


if __name__ == "__main__":
    main()

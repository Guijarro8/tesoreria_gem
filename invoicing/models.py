"""Validated invoice data and invoice calculations."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any


class InvoiceValidationError(ValueError):
    """Raised when invoice data cannot produce a valid invoice."""


class InvoiceKind(StrEnum):
    RESERVA = "Reserva"
    LIBRE = "Libre"


class Refuge(StrEnum):
    LA_LASTRA = "Casilla de la Lastra"
    EL_MORTERO = "Casilla del Mortero"

    @property
    def short_name(self) -> str:
        return {
            Refuge.LA_LASTRA: "Lastra",
            Refuge.EL_MORTERO: "Mortero",
        }[self]

    @property
    def display_name(self) -> str:
        return {
            Refuge.LA_LASTRA: "La Lastra",
            Refuge.EL_MORTERO: "El Mortero",
        }[self]


_CENTS = Decimal("0.01")
_CIF_PATTERN = re.compile(
    r"^(?:[A-Z]\d{7}[0-9A-J]|\d{8}[A-Z]|[XYZ]\d{7}[A-Z])$",
)


def _clean(value: str) -> str:
    return " ".join(value.split())


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return _clean(without_accents).casefold()


def _validate_common(
    *,
    official_name: str,
    address: str,
    tax_id: str,
    contact: str,
    vat_rate: Decimal,
) -> tuple[str, str, str, str, Decimal]:
    normalized_name = _clean(official_name)
    normalized_address = _clean(address)
    normalized_contact = _clean(contact)
    normalized_tax_id = re.sub(r"[\s-]+", "", tax_id).upper()
    required = {
        "Nombre": normalized_name,
        "Domicilio": normalized_address,
        "CIF": normalized_tax_id,
        "Contacto": normalized_contact,
    }
    missing = [label for label, value in required.items() if not value]
    if missing:
        raise InvoiceValidationError(
            "Faltan campos obligatorios: " + ", ".join(missing) + "."
        )
    if not Decimal(0) <= vat_rate <= Decimal(100):
        raise InvoiceValidationError("El tipo de IVA debe estar entre 0 y 100.")
    if not _CIF_PATTERN.fullmatch(normalized_tax_id):
        raise InvoiceValidationError(
            "El CIF no tiene un formato válido. Ejemplo: G82150103."
        )
    return (
        normalized_name,
        normalized_address,
        normalized_tax_id,
        normalized_contact,
        vat_rate,
    )


def _invoice_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _taxable_base(total: Decimal, vat_rate: Decimal) -> Decimal:
    divisor = Decimal(1) + vat_rate / Decimal(100)
    return (total / divisor).quantize(_CENTS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class Reservation:
    """Data required to calculate and render a reservation invoice."""

    official_name: str
    alias: str
    address: str
    tax_id: str
    contact: str
    starts_on: date
    ends_on: date
    refuge: Refuge
    participants: int
    rate_per_participant: Decimal
    vat_rate: Decimal

    @property
    def kind(self) -> InvoiceKind:
        return InvoiceKind.RESERVA

    @property
    def nights(self) -> int:
        # A same-day reservation is billed as one stay to avoid a zero invoice.
        return max(1, (self.ends_on - self.starts_on).days)

    @property
    def total_including_vat(self) -> Decimal:
        amount = self.nights * self.participants * self.rate_per_participant
        return amount.quantize(_CENTS, rounding=ROUND_HALF_UP)

    @property
    def taxable_base(self) -> Decimal:
        return _taxable_base(self.total_including_vat, self.vat_rate)

    @property
    def vat_amount(self) -> Decimal:
        return self.total_including_vat - self.taxable_base

    @property
    def invoice_hash(self) -> str:
        """Return a stable non-reversible key for detecting repeated submissions."""

        payload = {
            "kind": self.kind.value,
            "official_name": _fold(self.official_name),
            "alias": _fold(self.alias),
            "address": _fold(self.address),
            "tax_id": _fold(self.tax_id).replace(" ", "").replace("-", ""),
            "contact": _fold(self.contact),
            "starts_on": self.starts_on.isoformat(),
            "ends_on": self.ends_on.isoformat(),
            "refuge": self.refuge.value,
            "participants": self.participants,
            "rate_per_participant": str(self.rate_per_participant),
            "vat_rate": str(self.vat_rate),
        }
        return _invoice_hash(payload)


@dataclass(frozen=True, slots=True)
class FreeInvoice:
    """Fully configurable invoice not tied to a reservation."""

    official_name: str
    custom_name: str
    address: str
    tax_id: str
    contact: str
    description: str
    invoice_date: date
    total_including_vat: Decimal
    vat_rate: Decimal

    @property
    def kind(self) -> InvoiceKind:
        return InvoiceKind.LIBRE

    @property
    def taxable_base(self) -> Decimal:
        return _taxable_base(self.total_including_vat, self.vat_rate)

    @property
    def vat_amount(self) -> Decimal:
        return self.total_including_vat - self.taxable_base

    @property
    def invoice_hash(self) -> str:
        payload = {
            "kind": self.kind.value,
            "official_name": _fold(self.official_name),
            "custom_name": _fold(self.custom_name),
            "address": _fold(self.address),
            "tax_id": _fold(self.tax_id).replace(" ", "").replace("-", ""),
            "contact": _fold(self.contact),
            "description": _fold(self.description),
            "invoice_date": self.invoice_date.isoformat(),
            "total_including_vat": str(self.total_including_vat),
            "vat_rate": str(self.vat_rate),
        }
        return _invoice_hash(payload)


InvoiceDocument = Reservation | FreeInvoice


def build_reservation(
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
    rate_per_participant: Decimal,
    vat_rate: Decimal,
) -> Reservation:
    """Normalize and validate form data before any external operation."""

    normalized_alias = _clean(alias)
    if not normalized_alias:
        raise InvoiceValidationError("Falta el campo obligatorio: Alias.")
    (
        normalized_name,
        normalized_address,
        normalized_tax_id,
        normalized_contact,
        normalized_vat,
    ) = _validate_common(
        official_name=official_name,
        address=address,
        tax_id=tax_id,
        contact=contact,
        vat_rate=vat_rate,
    )
    if starts_on > ends_on:
        raise InvoiceValidationError(
            "La fecha de fin no puede ser anterior a la fecha de inicio."
        )
    if participants < 1:
        raise InvoiceValidationError("Debe haber al menos un participante.")
    if rate_per_participant <= 0:
        raise InvoiceValidationError(
            "La cuota por participante debe ser mayor que cero."
        )

    return Reservation(
        official_name=normalized_name,
        alias=normalized_alias,
        address=normalized_address,
        tax_id=normalized_tax_id,
        contact=normalized_contact,
        starts_on=starts_on,
        ends_on=ends_on,
        refuge=refuge,
        participants=participants,
        rate_per_participant=rate_per_participant.quantize(
            _CENTS,
            rounding=ROUND_HALF_UP,
        ),
        vat_rate=normalized_vat,
    )


def build_free_invoice(
    *,
    official_name: str,
    custom_name: str,
    address: str,
    tax_id: str,
    contact: str,
    description: str,
    invoice_date: date,
    total_including_vat: Decimal,
    vat_rate: Decimal,
) -> FreeInvoice:
    """Normalize and validate a fully configurable invoice."""

    normalized_custom_name = _clean(custom_name)
    normalized_description = " ".join(description.split())
    if not normalized_custom_name:
        raise InvoiceValidationError("Falta el nombre personalizado de carpeta y PDF.")
    if len(normalized_custom_name) > 90:
        raise InvoiceValidationError(
            "El nombre personalizado no puede superar 90 caracteres."
        )
    if not normalized_description:
        raise InvoiceValidationError("La descripción es obligatoria.")
    if len(normalized_description) > 1_000:
        raise InvoiceValidationError("La descripción no puede superar 1000 caracteres.")
    normalized_total = total_including_vat.quantize(
        _CENTS,
        rounding=ROUND_HALF_UP,
    )
    if normalized_total <= 0:
        raise InvoiceValidationError("El importe total debe ser mayor que cero.")
    (
        normalized_name,
        normalized_address,
        normalized_tax_id,
        normalized_contact,
        normalized_vat,
    ) = _validate_common(
        official_name=official_name,
        address=address,
        tax_id=tax_id,
        contact=contact,
        vat_rate=vat_rate,
    )
    return FreeInvoice(
        official_name=normalized_name,
        custom_name=normalized_custom_name,
        address=normalized_address,
        tax_id=normalized_tax_id,
        contact=normalized_contact,
        description=normalized_description,
        invoice_date=invoice_date,
        total_including_vat=normalized_total,
        vat_rate=normalized_vat,
    )

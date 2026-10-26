"""Validated reservation data and invoice calculations."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum


class InvoiceValidationError(ValueError):
    """Raised when reservation data cannot produce a valid invoice."""


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
    def nights(self) -> int:
        # A same-day reservation is billed as one stay to avoid a zero invoice.
        return max(1, (self.ends_on - self.starts_on).days)

    @property
    def total_including_vat(self) -> Decimal:
        amount = self.nights * self.participants * self.rate_per_participant
        return amount.quantize(_CENTS, rounding=ROUND_HALF_UP)

    @property
    def taxable_base(self) -> Decimal:
        divisor = Decimal(1) + self.vat_rate / Decimal(100)
        return (self.total_including_vat / divisor).quantize(
            _CENTS,
            rounding=ROUND_HALF_UP,
        )

    @property
    def vat_amount(self) -> Decimal:
        return self.total_including_vat - self.taxable_base

    @property
    def reservation_hash(self) -> str:
        """Return a stable non-reversible key for detecting repeated submissions."""

        payload = {
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
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


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

    normalized_name = _clean(official_name)
    normalized_alias = _clean(alias)
    normalized_address = _clean(address)
    normalized_contact = _clean(contact)
    normalized_tax_id = re.sub(r"[\s-]+", "", tax_id).upper()

    required = {
        "Nombre": normalized_name,
        "Alias": normalized_alias,
        "Domicilio": normalized_address,
        "CIF": normalized_tax_id,
        "Contacto": normalized_contact,
    }
    missing = [label for label, value in required.items() if not value]
    if missing:
        raise InvoiceValidationError(
            "Faltan campos obligatorios: " + ", ".join(missing) + "."
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
    if not Decimal(0) <= vat_rate <= Decimal(100):
        raise InvoiceValidationError("El tipo de IVA debe estar entre 0 y 100.")
    if not _CIF_PATTERN.fullmatch(normalized_tax_id):
        raise InvoiceValidationError(
            "El CIF no tiene un formato válido. Ejemplo: G82150103."
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
        vat_rate=vat_rate,
    )

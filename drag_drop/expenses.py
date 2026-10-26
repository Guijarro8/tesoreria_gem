"""Classify expense movements using stable merchant and concept patterns."""

from __future__ import annotations

import re
from numbers import Real
from typing import Literal

from . import constants
from .members import normalize_name

type ExpenseCategory = Literal[
    "Alquiler",
    "Electricidad",
    "Comisiones bancarias",
    "Seguros",
    "Otros",
]

RENT_AMOUNT = -372.23
RENT_CONCEPT = re.compile(
    r"a canal de isabel ii\s*,\s*s\.\s*a\.\s*,\s*m\.\s*p\.",
)


def classify_expense(concept: object, amount: object) -> ExpenseCategory:
    """Return the report category for an expense movement."""
    text = str(concept).strip().casefold()
    normalized = normalize_name(text)
    numeric_amount = float(amount) if isinstance(amount, Real) else 0.0

    if "canal de isabel ii" in normalized:
        if RENT_CONCEPT.search(text) or abs(numeric_amount - RENT_AMOUNT) < 0.005:
            return constants.EXPENSE_RENT
        return constants.EXPENSE_ELECTRICITY
    if "comision" in normalized:
        return constants.EXPENSE_BANK_FEES
    if "seguros helvetia" in normalized:
        return constants.EXPENSE_INSURANCE
    return constants.EXPENSE_OTHER

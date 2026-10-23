"""Tests for expense classification and report categories."""

import pytest

from drag_drop import constants, expenses


@pytest.mark.parametrize(
    ("concept", "amount", "expected"),
    [
        (
            "A CANAL DE ISABEL II, S.A., M.P.",
            -372.23,
            constants.EXPENSE_RENT,
        ),
        (
            "a canal de isabel ii sa mp",
            -84.50,
            constants.EXPENSE_ELECTRICITY,
        ),
        (
            "intereses y/o comisiones cuenta",
            -12.00,
            constants.EXPENSE_BANK_FEES,
        ),
        (
            "comisiones",
            -3.50,
            constants.EXPENSE_BANK_FEES,
        ),
        (
            "seguros helvetia",
            -45.00,
            constants.EXPENSE_INSURANCE,
        ),
        (
            "material de oficina",
            -20.00,
            constants.EXPENSE_OTHER,
        ),
    ],
)
def test_classify_expense(
    concept: str,
    amount: float,
    expected: str,
) -> None:
    assert expenses.classify_expense(concept, amount) == expected


def test_fixed_rent_amount_distinguishes_ambiguous_canal_concepts() -> None:
    assert (
        expenses.classify_expense(
            "a canal de isabel ii s a m p",
            -372.23,
        )
        == constants.EXPENSE_RENT
    )
    assert (
        expenses.classify_expense(
            "a canal de isabel ii s a m p",
            -81.10,
        )
        == constants.EXPENSE_ELECTRICITY
    )

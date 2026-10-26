"""Unit tests for member-directory validation and alias matching."""

import pandas as pd
import pytest

from drag_drop import constants, members


def member_rows() -> list[dict[str, object]]:
    return [
        {
            "Nombre": "Synthetic Member A",
            "Estado": "activo",
            "Alias 1": "synthetic alias a",
            "Alias 2": "",
        },
        {
            "Nombre": "Synthetic Member B",
            "Estado": "activo",
            "Alias 1": "synthetic alias b",
            "Alias 2": "",
        },
    ]


def settings_rows() -> list[dict[str, object]]:
    return [
        {
            "Parámetro": constants.SETTING_INACTIVE_AFTER_MONTHS,
            "Valor": 12,
        },
        {
            "Parámetro": constants.SETTING_SINGLE_PAYMENT_GRACE_MONTHS,
            "Valor": 3,
        },
    ]


def test_normalize_name_removes_accents_punctuation_and_spacing() -> None:
    assert members.normalize_name("  Ánä  de-la  Peña. ") == "ana de la pena"


def test_directory_maps_all_alias_columns_to_the_same_member() -> None:
    directory = members.build_member_directory(member_rows(), settings_rows())

    assert directory.aliases["synthetic member a"] == "Synthetic Member A"
    assert directory.aliases["synthetic alias a"] == "Synthetic Member A"
    assert directory.settings.inactive_after_months == 12
    assert directory.settings.single_payment_grace_months == 3
    assert directory.suspicious_aliases == {}


def test_directory_rejects_duplicate_member_names() -> None:
    duplicate_rows = member_rows()
    duplicate_rows[1]["Nombre"] = duplicate_rows[0]["Nombre"]

    with pytest.raises(ValueError, match="Duplicate member"):
        members.build_member_directory(duplicate_rows, settings_rows())


def test_matching_uses_aliases_and_reports_unresolved_fee_payments() -> None:
    directory = members.build_member_directory(member_rows(), settings_rows())
    movements = pd.DataFrame(
        {
            "concepto": [
                "synthetic alias a",
                "synthetic member b",
                "unknown alias",
            ],
            "tipo": ["cuota", "cuota", "cuota"],
        }
    )

    matched, report = members.match_movements(movements, directory)

    assert matched["miembro"].iloc[0] == "Synthetic Member A"
    assert matched["miembro"].iloc[1] == "Synthetic Member B"
    assert pd.isna(matched["miembro"].iloc[2])
    assert report.matched_fee_payments == 2
    assert report.unmatched_aliases == ("unknown alias",)
    assert report.ambiguous_aliases == ()
    assert report.suspicious_aliases == ()


def test_ambiguous_aliases_are_not_assigned_to_a_member() -> None:
    rows = member_rows()
    rows[1]["Alias 2"] = "shared synthetic alias"
    rows[0]["Alias 2"] = "shared synthetic alias"
    directory = members.build_member_directory(rows, settings_rows())
    movements = pd.DataFrame(
        {
            "concepto": ["shared synthetic alias"],
            "tipo": ["cuota"],
        }
    )

    matched, report = members.match_movements(movements, directory)

    assert pd.isna(matched["miembro"].iloc[0])
    assert report.matched_fee_payments == 0
    assert report.ambiguous_aliases == ("shared synthetic alias",)
    assert report.suspicious_aliases == ()


def test_alias_similar_to_another_member_is_flagged_and_not_matched() -> None:
    rows = member_rows()
    rows[0]["Alias 2"] = "synthetic member bee"
    directory = members.build_member_directory(rows, settings_rows())
    movements = pd.DataFrame(
        {
            "concepto": ["synthetic member bee"],
            "tipo": ["cuota"],
        }
    )

    matched, report = members.match_movements(movements, directory)

    assert pd.isna(matched["miembro"].iloc[0])
    assert report.matched_fee_payments == 0
    assert report.suspicious_aliases == ("synthetic member bee",)

"""Load and apply the private member identity directory."""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, cast

import gspread
import pandas as pd

from . import constants

type MemberStatus = Literal["activo", "inactivo"]


@dataclass(frozen=True)
class Member:
    """A confirmed member and the transfer names that identify them."""

    name: str
    status: MemberStatus
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class DirectorySettings:
    """Business rules loaded from the private member directory."""

    inactive_after_months: int
    single_payment_grace_months: int


@dataclass(frozen=True)
class MemberDirectory:
    """Validated membership data used for in-memory transfer matching."""

    members: tuple[Member, ...]
    exact_aliases: Mapping[str, str]
    aliases: Mapping[str, str]
    ambiguous_exact_aliases: Mapping[str, tuple[str, ...]]
    ambiguous_aliases: Mapping[str, tuple[str, ...]]
    settings: DirectorySettings

    @property
    def members_by_name(self) -> Mapping[str, Member]:
        """Return members keyed by their canonical display name."""
        return {member.name: member for member in self.members}


@dataclass(frozen=True)
class MatchingReport:
    """Summary of fee-like transfers that could not be matched safely."""

    matched_fee_payments: int
    unmatched_aliases: tuple[str, ...]
    ambiguous_aliases: tuple[str, ...]


def normalize_name(value: object) -> str:
    """Normalize accents, punctuation, whitespace, and casing for fallback matching."""
    if not isinstance(value, str):
        return ""

    without_accents = _without_accents(value)
    cleaned = "".join(
        character if character.isalnum() else " " for character in without_accents
    )
    return " ".join(cleaned.split())


def normalize_exact_name(value: object) -> str:
    """Normalize accents, casing, and whitespace while preserving punctuation."""
    if not isinstance(value, str):
        return ""
    return " ".join(_without_accents(value).split())


def _without_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )


def _build_alias_lookup(
    members: Sequence[Member],
    normalizer: Callable[[object], str],
) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    alias_owners: defaultdict[str, set[str]] = defaultdict(set)
    for member in members:
        for alias in (member.name, *member.aliases):
            normalized_alias = normalizer(alias)
            if normalized_alias:
                alias_owners[normalized_alias].add(member.name)

    aliases: dict[str, str] = {}
    ambiguous_aliases: dict[str, tuple[str, ...]] = {}
    for normalized_alias, owners in alias_owners.items():
        if len(owners) == 1:
            aliases[normalized_alias] = next(iter(owners))
        else:
            ambiguous_aliases[normalized_alias] = tuple(sorted(owners))
    return aliases, ambiguous_aliases


def _parse_positive_int(value: object, setting_name: str) -> int:
    try:
        parsed = int(str(value).strip())
    except ValueError as error:
        raise ValueError(f"Invalid integer setting: {setting_name}") from error
    if parsed <= 0:
        raise ValueError(f"Setting must be positive: {setting_name}")
    return parsed


def build_member_directory(
    member_rows: Sequence[Mapping[str, object]],
    settings_rows: Sequence[Mapping[str, object]],
) -> MemberDirectory:
    """Validate human-maintained member and settings rows."""
    members: list[Member] = []
    seen_names: set[str] = set()

    for row in member_rows:
        name = str(row.get("Nombre", "")).strip()
        if not name:
            continue

        normalized_name = normalize_name(name)
        if not normalized_name:
            raise ValueError("A member name has no comparable characters.")
        if normalized_name in seen_names:
            raise ValueError("Duplicate member name in the directory.")
        seen_names.add(normalized_name)

        status_value = str(row.get("Estado", "")).strip().casefold()
        if status_value not in {"activo", "inactivo"}:
            raise ValueError("Member status must be activo or inactivo.")

        aliases = tuple(
            str(value).strip()
            for header, value in row.items()
            if str(header).casefold().startswith("alias")
            and value is not None
            and str(value).strip()
        )
        members.append(
            Member(
                name=name,
                status=status_value,
                aliases=aliases,
            )
        )

    if not members:
        raise ValueError("The member directory has no member rows.")

    exact_aliases, ambiguous_exact_aliases = _build_alias_lookup(
        members,
        normalize_exact_name,
    )
    aliases, ambiguous_aliases = _build_alias_lookup(members, normalize_name)

    settings = {
        str(row.get("Parámetro", "")).strip(): row.get("Valor") for row in settings_rows
    }
    directory_settings = DirectorySettings(
        inactive_after_months=_parse_positive_int(
            settings.get(
                constants.SETTING_INACTIVE_AFTER_MONTHS,
                constants.DEFAULT_INACTIVE_AFTER_MONTHS,
            ),
            constants.SETTING_INACTIVE_AFTER_MONTHS,
        ),
        single_payment_grace_months=_parse_positive_int(
            settings.get(
                constants.SETTING_SINGLE_PAYMENT_GRACE_MONTHS,
                constants.DEFAULT_SINGLE_PAYMENT_GRACE_MONTHS,
            ),
            constants.SETTING_SINGLE_PAYMENT_GRACE_MONTHS,
        ),
    )

    return MemberDirectory(
        members=tuple(members),
        exact_aliases=exact_aliases,
        aliases=aliases,
        ambiguous_exact_aliases=ambiguous_exact_aliases,
        ambiguous_aliases=ambiguous_aliases,
        settings=directory_settings,
    )


def load_member_directory(spreadsheet: gspread.Spreadsheet) -> MemberDirectory:
    """Load the directory using the tabs documented for human editors."""
    members_sheet = spreadsheet.worksheet(constants.MEMBER_DIRECTORY_TAB)
    settings_sheet = spreadsheet.worksheet(constants.MEMBER_SETTINGS_TAB)

    member_rows = cast(
        list[Mapping[str, object]],
        members_sheet.get_all_records(),
    )
    settings_rows = cast(
        list[Mapping[str, object]],
        settings_sheet.get_all_records(),
    )
    return build_member_directory(member_rows, settings_rows)


def match_movements(
    movements: pd.DataFrame,
    directory: MemberDirectory,
) -> tuple[pd.DataFrame, MatchingReport]:
    """Attach canonical member names and report only unresolved fee payments."""
    matched = movements.copy()
    exact_concepts = matched["concepto"].map(normalize_exact_name)
    normalized_concepts = matched["concepto"].map(normalize_name)

    exact_assignment = exact_concepts.map(directory.exact_aliases)
    fallback_mask = exact_assignment.isna() & ~exact_concepts.isin(
        directory.ambiguous_exact_aliases
    )
    fallback_assignment = normalized_concepts.map(directory.aliases)
    matched["miembro"] = exact_assignment
    matched.loc[fallback_mask, "miembro"] = fallback_assignment.loc[fallback_mask]

    fee_mask = matched["tipo"] == "cuota"
    matched_mask = matched["miembro"].notna()
    ambiguous_mask = exact_concepts.isin(directory.ambiguous_exact_aliases) | (
        fallback_mask & normalized_concepts.isin(directory.ambiguous_aliases)
    )
    unknown_mask = fee_mask & ~matched_mask & ~ambiguous_mask

    unmatched_aliases = tuple(
        sorted(matched.loc[unknown_mask, "concepto"].astype(str).unique())
    )
    ambiguous_aliases = tuple(
        sorted(matched.loc[ambiguous_mask & fee_mask, "concepto"].astype(str).unique())
    )
    report = MatchingReport(
        matched_fee_payments=int((fee_mask & matched_mask).sum()),
        unmatched_aliases=unmatched_aliases,
        ambiguous_aliases=ambiguous_aliases,
    )
    return matched, report

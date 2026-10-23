"""Regenerate the configured production workbook from a private bank export."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

import gspread

from drag_drop import exclusions, finance_report, members, utils


def latest_bank_export() -> Path:
    candidates = sorted(
        Path("private").glob("*.xls"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No .xls bank export found under private/.")
    return candidates[0]


def load_secrets() -> dict[str, Any]:
    return tomllib.loads(Path(".streamlit/secrets.toml").read_text())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        help="Optional bank export path; defaults to the newest private/*.xls.",
    )
    args = parser.parse_args()

    source = args.source or latest_bank_export()
    if not source.is_file():
        raise FileNotFoundError(f"Bank export not found: {source}")

    secrets = load_secrets()
    credentials = json.loads(str(secrets["gcp_credentials"]))
    client = gspread.service_account_from_dict(credentials)
    output = client.open_by_key(str(secrets["tesoreria_gem_key"]))
    directory = members.load_member_directory(
        client.open_by_key(str(secrets["tesoreria_members_key"]))
    )
    excluded_ids = exclusions.load_exclusion_ids(output)

    with source.open("rb") as handle:
        processed = utils.process_file(handle, directory, excluded_ids)

    blocking_issues = len(processed.report.matching.ambiguous_aliases) + len(
        processed.report.matching.suspicious_aliases
    )
    if blocking_issues:
        print(f"Refusing to update: {blocking_issues} alias conflicts found.")
        return 1

    utils.upload_dataframes(processed.dataframes, output)
    finance_report.ensure_finance_report_sheet(
        output,
        processed.dataframes["general"],
    )

    exclusion_report = processed.exclusions
    print(f"Source: {source.name}")
    print(f"Movements retained: {len(processed.dataframes['general'])}")
    print(f"Fee rows: {len(processed.dataframes['cuotas'])}")
    print(f"Marshill transactions excluded: {exclusion_report.matched_transactions}")
    marshill_net = exclusion_report.excluded_income - exclusion_report.excluded_expenses
    print(f"Marshill net excluded: {marshill_net:.2f} EUR")
    if exclusion_report.unmatched_ids:
        print(
            "Warning: "
            f"{len(exclusion_report.unmatched_ids)} Marshill IDs were not found."
        )
    if processed.report.matching.unmatched_aliases:
        unmatched_alias_count = len(processed.report.matching.unmatched_aliases)
        print(f"Warning: {unmatched_alias_count} fee aliases were unmatched.")
    print("Production workbook regenerated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

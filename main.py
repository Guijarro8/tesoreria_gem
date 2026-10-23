import json
from typing import Any, cast

import gspread
import streamlit as st

from drag_drop import constants, exclusions, finance_report, members, utils


def _read_secret(name: str) -> str:
    if name not in st.secrets:
        raise ValueError(f"Missing secret: {name}")
    return str(st.secrets[name])


def _load_member_directory() -> tuple[
    gspread.Client,
    members.MemberDirectory,
    str,
]:
    credentials = cast(
        dict[str, Any],
        json.loads(_read_secret("gcp_credentials")),
    )
    client = gspread.service_account_from_dict(credentials)
    directory_key = _read_secret("tesoreria_members_key")
    spreadsheet = client.open_by_key(directory_key)
    return client, members.load_member_directory(spreadsheet), directory_key


def _show_names(label: str, names: tuple[str, ...]) -> None:
    if names:
        with st.expander(f"{label} ({len(names)})"):
            st.write("\n".join(names))


def _show_report(report: utils.FeeReport) -> None:
    matching = report.matching
    if report.as_of is not None:
        st.caption(f"Fecha de referencia: {report.as_of:%Y-%m-%d}")
    st.metric("Pagos de cuota reconocidos", matching.matched_fee_payments)
    _show_names("Transferencias de cuota sin identificar", matching.unmatched_aliases)
    _show_names("Alias ambiguos", matching.ambiguous_aliases)
    _show_names(
        "Alias posiblemente asignados a otro socio",
        matching.suspicious_aliases,
    )
    _show_names("Socios excluidos como inactivos", report.excluded_inactive_members)
    _show_names(
        "Pagos únicos antiguos excluidos",
        report.excluded_old_single_payments,
    )
    _show_names("Socios sin cuota en 12 meses", report.excluded_stale_members)

    if matching.ambiguous_aliases or matching.suspicious_aliases:
        st.error(
            "Hay alias ambiguos o muy parecidos al nombre de otro socio. Corrige "
            "el directorio antes de actualizar la hoja."
        )
    elif matching.unmatched_aliases:
        st.warning(
            "Hay transferencias parecidas a cuotas que no están asociadas a ningún "
            "socio. Revisa el directorio si alguna debe incluirse."
        )


def _show_exclusions(report: exclusions.ExclusionReport) -> None:
    if report.configured_ids == 0:
        return

    st.metric(
        "Movimientos excluidos · Marshill (Sudáfrica)",
        report.matched_transactions,
    )
    st.caption(
        f"Ingresos excluidos: {report.excluded_income:,.2f} € · "
        f"Gastos excluidos: {report.excluded_expenses:,.2f} €"
    )
    if report.unmatched_ids:
        st.warning(
            f"{len(report.unmatched_ids)} identificadores de Marshill (Sudáfrica) "
            "no aparecen en el extracto actual."
        )


def main() -> None:
    """Render the Streamlit application."""
    st.title("Drag & Drop Excel de Tesorería GEM")

    uploaded_file = st.file_uploader("Upload an Excel file", type=["xls"])

    if uploaded_file is None:
        return

    st.write(f"Uploaded file: {uploaded_file.name}")

    try:
        client, directory, directory_key = _load_member_directory()
        tesoreria_gem_key = _read_secret("tesoreria_gem_key")
        spreadsheet = client.open_by_key(tesoreria_gem_key)
        excluded_ids = exclusions.load_exclusion_ids(spreadsheet)
        processed = utils.process_file(
            uploaded_file,
            directory,
            excluded_ids,
        )
    except (KeyError, ValueError, gspread.GSpreadException):
        st.error(
            "No se pudo leer el directorio de socios o el archivo de movimientos. "
            "Revisa la configuración y los encabezados de las hojas."
        )
        return

    st.link_button(
        "Abrir directorio de socios",
        f"https://docs.google.com/spreadsheets/d/{directory_key}/edit",
    )
    st.link_button(
        "Abrir Marshill (Sudáfrica)",
        f"https://docs.google.com/spreadsheets/d/{tesoreria_gem_key}/edit"
        f"#gid={spreadsheet.worksheet(constants.PROJECT_EXCLUSIONS_TAB).id}",
    )
    _show_report(processed.report)
    _show_exclusions(processed.exclusions)

    if st.button(
        "Replace Existing File",
        disabled=bool(
            processed.report.matching.ambiguous_aliases
            or processed.report.matching.suspicious_aliases
        ),
    ):
        try:
            utils.upload_dataframes(processed.dataframes, spreadsheet)
            finance_report.ensure_finance_report_sheet(
                spreadsheet,
                processed.dataframes["general"],
            )
        except (KeyError, ValueError, gspread.GSpreadException):
            st.error("No se pudo actualizar la hoja de cálculo.")
            return

        st.success(
            "The existing file has been successfully replaced! "
            "https://docs.google.com/spreadsheets/d/"
            f"{tesoreria_gem_key}/edit?gid=0#gid=0"
        )


if __name__ == "__main__":
    main()

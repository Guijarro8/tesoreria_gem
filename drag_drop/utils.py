"""Transform bank-movement workbooks and publish the results to Google Sheets."""

import hashlib
from collections.abc import Set
from dataclasses import dataclass
from numbers import Real
from typing import BinaryIO, Literal, cast

import gspread
import pandas as pd

from . import constants, exclusions, expenses, members

type DataFramesToUpload = dict[str, pd.DataFrame]
type MovementKind = Literal["cuota", "gasto", "varios"]

CUOTAS_POSIBLES = frozenset(
    cuota * payments for payments in range(1, 8) for cuota in constants.CUOTAS
)


@dataclass(frozen=True)
class FeeReport:
    """Reconciliation details shown before an upload."""

    matching: members.MatchingReport
    excluded_inactive_members: tuple[str, ...]
    excluded_old_single_payments: tuple[str, ...]
    excluded_stale_members: tuple[str, ...]
    as_of: pd.Timestamp | None


@dataclass(frozen=True)
class ProcessedFile:
    """Processed tables and their reconciliation report."""

    dataframes: DataFramesToUpload
    report: FeeReport
    exclusions: exclusions.ExclusionReport


def extract_cuotas(
    df_movements: pd.DataFrame,
    directory: members.MemberDirectory,
    matching_report: members.MatchingReport,
) -> tuple[pd.DataFrame, FeeReport]:
    """Aggregate confirmed fee payments by member and month."""
    fee_movements = df_movements[
        (df_movements["tipo"] == "cuota") & df_movements["miembro"].notna()
    ].copy()

    dates = pd.to_datetime(df_movements["fecha"]).dropna()
    as_of = cast(pd.Timestamp, dates.max()) if not dates.empty else None
    eligible_members: set[str] = set()
    excluded_inactive: list[str] = []
    excluded_single: list[str] = []
    excluded_stale: list[str] = []

    if as_of is not None:
        single_payment_cutoff = as_of - pd.DateOffset(
            months=directory.settings.single_payment_grace_months
        )
        inactive_cutoff = as_of - pd.DateOffset(
            months=directory.settings.inactive_after_months
        )
        members_by_name = directory.members_by_name

        for member_name, payments in fee_movements.groupby("miembro", sort=True):
            member = members_by_name[str(member_name)]
            latest_payment = cast(pd.Timestamp, payments["fecha"].max())

            if member.status == "inactivo":
                excluded_inactive.append(member.name)
            elif len(payments) == 1 and latest_payment < single_payment_cutoff:
                excluded_single.append(member.name)
            elif latest_payment < inactive_cutoff:
                excluded_stale.append(member.name)
            else:
                eligible_members.add(member.name)

    eligible_movements = fee_movements[fee_movements["miembro"].isin(eligible_members)]
    grouped_data = (
        eligible_movements.groupby(["miembro", "mes_anio"], sort=True)
        .agg(importe_sum=("importe", "sum"))
        .reset_index()
    )
    pivot_table = grouped_data.pivot(
        index="miembro", columns="mes_anio", values="importe_sum"
    ).reset_index()
    pivot_table = pivot_table.sort_values(
        "miembro",
        key=lambda names: names.map(members.normalize_name),
        kind="stable",
    ).reset_index(drop=True)

    period_columns = pivot_table.columns[1:]

    # El importe total pagado
    pivot_table["importe_pagado_total"] = pivot_table.loc[:, period_columns].sum(
        axis=1, skipna=True
    )

    # conteo de null para obtener el número de cuotas pagadas
    pivot_table["numero_cuotas_pagadas"] = len(period_columns) - (
        pivot_table.loc[:, period_columns].isna().sum(axis=1)
    )

    df_cuotas = pivot_table[
        ["miembro"]
        + [col for col in list(pivot_table.columns)[::-1] if col != "miembro"]
    ]

    report = FeeReport(
        matching=matching_report,
        excluded_inactive_members=tuple(excluded_inactive),
        excluded_old_single_payments=tuple(excluded_single),
        excluded_stale_members=tuple(excluded_stale),
        as_of=as_of,
    )
    return cast(pd.DataFrame, df_cuotas), report


def _classify_movement(amount: object) -> MovementKind:
    """Classify a movement from its signed amount."""
    if not isinstance(amount, Real):
        return "varios"
    if amount in CUOTAS_POSIBLES:
        return "cuota"
    if amount < 0:
        return "gasto"
    return "varios"


def _movement_ids(raw_movements: pd.DataFrame) -> list[str]:
    source_columns = [
        "F. Operativa",
        "Concepto",
        "F. Valor",
        "Importe",
        "Saldo",
        "Referencia 1",
        "Referencia 2",
    ]
    source_values = raw_movements.reindex(columns=source_columns).fillna("").astype(str)
    fingerprints = source_values.agg("\x1f".join, axis=1)
    occurrences = fingerprints.groupby(fingerprints).cumcount() + 1
    return [
        hashlib.sha256(f"{fingerprint}\x1f{occurrence}".encode()).hexdigest()[:24]
        for fingerprint, occurrence in zip(fingerprints, occurrences, strict=True)
    ]


def prepare_movements(raw_movements: pd.DataFrame) -> pd.DataFrame:
    """Normalize raw worksheet data and classify each bank movement."""
    raw_movements = raw_movements.copy()
    raw_movements[constants.MOVEMENT_ID_COLUMN] = _movement_ids(raw_movements)
    df_movements = raw_movements.rename(columns=constants.COLUMNS_RENAME["raw"])
    for reference_column in ("referencia_1", "referencia_2"):
        if reference_column not in df_movements:
            df_movements[reference_column] = ""
    df_movements = df_movements[
        [
            "fecha",
            "concepto",
            "importe",
            "saldo",
            "referencia_1",
            "referencia_2",
            constants.MOVEMENT_ID_COLUMN,
        ]
    ]
    df_movements["fecha"] = pd.to_datetime(df_movements["fecha"], format="%d/%m/%Y")
    df_movements["mes_anio"] = df_movements["fecha"].dt.to_period("M").astype(str)
    df_movements["tipo"] = df_movements["importe"].map(_classify_movement)

    df_movements["concepto"] = df_movements["concepto"].astype(str)
    for word in ["ABONO", "TRANSFERENCIA", "RECIBO", "PAGO"]:
        df_movements["concepto"] = (
            df_movements["concepto"].str.replace(word, "", case=False).str.strip()
        )
    df_movements["concepto"] = df_movements["concepto"].apply(
        lambda x: x[3:] if x.startswith("DE ") else x
    )
    df_movements["concepto"] = df_movements["concepto"].str.lower()
    df_movements[constants.EXPENSE_CATEGORY_COLUMN] = [
        expenses.classify_expense(concept, amount) if movement_type == "gasto" else ""
        for concept, amount, movement_type in zip(
            df_movements["concepto"],
            df_movements["importe"],
            df_movements["tipo"],
            strict=True,
        )
    ]

    return cast(pd.DataFrame, df_movements)


def process_file(
    uploaded_file: BinaryIO,
    directory: members.MemberDirectory,
    excluded_ids: Set[str] = frozenset(),
) -> ProcessedFile:
    """Read an uploaded workbook and return tables destined for Google Sheets."""
    raw_movements = pd.read_excel(uploaded_file, skiprows=8)
    df_movements = prepare_movements(raw_movements)
    df_movements, exclusion_report = exclusions.apply_exclusions(
        df_movements,
        excluded_ids,
    )
    matched_movements, matching_report = members.match_movements(
        df_movements,
        directory,
    )
    matched_movements = matched_movements[
        [
            "fecha",
            "concepto",
            "importe",
            "saldo",
            "mes_anio",
            "tipo",
            constants.EXPENSE_CATEGORY_COLUMN,
            "miembro",
            "referencia_1",
            "referencia_2",
            constants.MOVEMENT_ID_COLUMN,
        ]
    ]

    # Calcular cuotas por socio en base al importe de la cuota
    df_cuotas, report = extract_cuotas(
        matched_movements,
        directory,
        matching_report,
    )

    # DataFrames seleccionados y en orden para subir
    dataframes = {
        "cuotas": df_cuotas,
        "general": matched_movements,
        "gasto": matched_movements.loc[matched_movements["tipo"] == "gasto"],
        "varios": matched_movements.loc[matched_movements["tipo"] == "varios"],
    }
    return ProcessedFile(
        dataframes=dataframes,
        report=report,
        exclusions=exclusion_report,
    )


def upload_dataframes(
    dataframes: DataFramesToUpload,
    spreadsheet: gspread.Spreadsheet,
) -> None:
    """Replace the first four worksheets with the supplied DataFrames."""

    for df_name, dataframe in dataframes.items():
        # Renombramos colunas con nombres bonitos
        if new_cols := constants.COLUMNS_RENAME.get(df_name):
            dataframe = dataframe.rename(columns=new_cols)

        # llenar nulos con vacio
        dataframe = dataframe.fillna("-")
        # borrar formato fecha
        if df_name != "cuotas":
            dataframe["fecha"] = dataframe["fecha"].astype(str)

        # Formatear y subir a google sheets
        formatted_data = cast(
            list[list[object]],
            [dataframe.columns.tolist(), *dataframe.values.tolist()],
        )
        worksheet = spreadsheet.worksheet(constants.OUTPUT_WORKSHEET_TABS[df_name])

        worksheet.clear()
        worksheet.update(formatted_data)

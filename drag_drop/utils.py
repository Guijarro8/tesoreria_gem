"""Transform bank-movement workbooks and publish the results to Google Sheets."""

from numbers import Real
from typing import BinaryIO, Literal, cast

import gspread
import pandas as pd

from . import constants

type DataFramesToUpload = dict[str, pd.DataFrame]
type MovementKind = Literal["cuota", "gasto", "varios"]

CUOTAS_POSIBLES = frozenset(
    cuota * payments for payments in range(1, 8) for cuota in constants.CUOTAS
)


def extract_cuotas(df_movements: pd.DataFrame) -> pd.DataFrame:
    """Aggregate payments by member and month.

    Members with only one recorded payment are excluded because a single amount
    matching a fee may instead be an expense, refund, or group contribution.
    """
    grouped_data = (
        df_movements[df_movements["tipo"] == "cuota"]
        .groupby(["concepto", "mes_anio"])
        .agg(importe_sum=("importe", "sum"))
        .reset_index()
    )

    # pivot para generar el formato que queremos
    pivot_table = grouped_data.pivot(
        index="concepto", columns="mes_anio", values="importe_sum"
    ).reset_index()

    period_columns = pivot_table.columns[1:]

    # El importe total pagado
    pivot_table["importe_pagado_total"] = pivot_table.loc[:, period_columns].sum(
        axis=1, skipna=True
    )

    # conteo de null para obtener el número de cuotas pagadas
    pivot_table["numero_cuotas_pagadas"] = len(period_columns) - (
        pivot_table.loc[:, period_columns].isna().sum(axis=1)
    )

    # Sólo consideramos a los socios que han pagado más de una cuota
    # para evitar incluir aportaciones de salidas, ingresos de grupos, etc
    pivot_table = pivot_table.loc[pivot_table["numero_cuotas_pagadas"] > 1]
    df_cuotas = pivot_table[
        ["concepto"]
        + [col for col in list(pivot_table.columns)[::-1] if col != "concepto"]
    ]

    return cast(pd.DataFrame, df_cuotas)


def _classify_movement(amount: object) -> MovementKind:
    """Classify a movement from its signed amount."""
    if not isinstance(amount, Real):
        return "varios"
    if amount in CUOTAS_POSIBLES:
        return "cuota"
    if amount < 0:
        return "gasto"
    return "varios"


def prepare_movements(raw_movements: pd.DataFrame) -> pd.DataFrame:
    """Normalize raw worksheet data and classify each bank movement."""
    df_movements = raw_movements.rename(columns=constants.COLUMNS_RENAME["raw"]).copy()
    df_movements = df_movements[["fecha", "concepto", "importe", "saldo"]]
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

    return cast(pd.DataFrame, df_movements)


def process_file(uploaded_file: BinaryIO) -> DataFramesToUpload:
    """Read an uploaded workbook and return tables destined for Google Sheets."""
    raw_movements = pd.read_excel(uploaded_file, skiprows=8)
    df_movements = prepare_movements(raw_movements)

    # Calcular cuotas por socio en base al importe de la cuota
    df_cuotas = extract_cuotas(df_movements)

    # DataFrames seleccionados y en orden para subir
    return {
        "cuotas": df_cuotas,
        "general": df_movements,
        "gasto": df_movements.loc[df_movements["tipo"] == "gasto"],
        "varios": df_movements.loc[df_movements["tipo"] == "varios"],
    }


def upload_dataframes(
    dataframes: DataFramesToUpload,
    spreadsheet: gspread.Spreadsheet,
) -> None:
    """Replace the first four worksheets with the supplied DataFrames."""

    for index, (df_name, dataframe) in enumerate(dataframes.items(), start=1):
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
        worksheet = spreadsheet.get_worksheet(index)
        if worksheet is None:
            raise ValueError(f"La hoja {index} no existe en la hoja de cálculo.")

        if df_name == "cuotas":
            # Mantener la primera columna para el join con nombres de socios
            worksheet.update(formatted_data, range_name="B1")
        else:
            worksheet.update(formatted_data)

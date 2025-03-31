import pandas as pd

from . import constants


def extract_cuotas(df_movements):
    """Extraer cuotas pagadas de los movimientos, por socio"""
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

    # El importe total pagado
    pivot_table["importe_pagado_total"] = pivot_table.iloc[:, 1:].sum(
        axis=1, skipna=True
    )

    # conteo de null para obtener el número de cuotas pagadas
    pivot_table["numero_cuotas_pagadas"] = (
        pivot_table.shape[1] - pivot_table.iloc[:, 1:].isna().sum(axis=1) - 2
    )

    # Sólo consideramos a los socios que han pagado más de una cuota
    # para evitar incluir aportaciones de salidas, ingresos de grupos, etc
    pivot_table = pivot_table.loc[pivot_table["numero_cuotas_pagadas"] > 1]
    df_cuotas = pivot_table[
        ["concepto"]
        + [col for col in list(pivot_table.columns)[::-1] if col != "concepto"]
    ]

    return df_cuotas


def process_file(uploaded_file):
    """Read the uploaded file and return processed DataFrames"""
    # Read the Excel file and save it as a CSV
    df_movements = pd.read_excel(uploaded_file, skiprows=8)

    # Formato y limpieza de datos
    df_movements = df_movements.rename(columns=constants.COLUMNS_RENAME["raw"])
    df_movements = df_movements[["fecha", "concepto", "importe", "saldo"]]
    df_movements["fecha"] = pd.to_datetime(df_movements["fecha"], format="%d/%m/%Y")
    df_movements["mes_anio"] = df_movements["fecha"].dt.to_period("M").astype(str)
    cuotas_posibles = set()
    for i in range(1, 8):
        # Hay personas que pagan varias cuotas, hasta 7
        for cuota in constants.CUOTAS:
            cuotas_posibles.add(cuota * i)
    df_movements["tipo"] = df_movements["importe"].apply(
        lambda x: "cuota" if x in cuotas_posibles else ("gasto" if x < 0 else "varios")
    )

    # tratamiento de concepto
    for word in ["ABONO", "TRANSFERENCIA", "RECIBO", "PAGO"]:
        df_movements["concepto"] = (
            df_movements["concepto"].str.replace(word, "", case=False).str.strip()
        )
    df_movements["concepto"] = df_movements["concepto"].apply(
        lambda x: x[3:] if x.startswith("DE ") else x
    )
    df_movements["concepto"] = df_movements["concepto"].str.lower()

    # Calcular cuotas por socio en base al importe de la cuota
    df_cuotas = extract_cuotas(df_movements)

    # DataFrames seleccionados y en orden para subir
    dfs_to_upload = {
        "cuotas": df_cuotas,
        "general": df_movements,
        "gasto": df_movements.loc[df_movements["tipo"] == "gasto"],
        "varios": df_movements.loc[df_movements["tipo"] == "varios"],
    }

    return dfs_to_upload


def upload_dataframes(dfs_to_upload, sheet):
    """Upload DataFrames to a Google Sheet"""

    for i, (df_name, df) in enumerate(dfs_to_upload.items(), start=1):
        # Renombramos colunas con nombres bonitos
        if new_cols := constants.COLUMNS_RENAME.get(df_name):
            df = df.rename(columns=new_cols)

        # llenar nulos con vacio
        df = df.fillna("-")
        # borrar formato fecha
        if df_name != "cuotas":
            df["fecha"] = df["fecha"].astype(str)

        # Formatear y subir a google sheets
        upload_formated_data = [df.columns.tolist()] + df.values.tolist()

        if df_name == "cuotas":
            # Mantener la primera columna para el join con nombres de socios
            sheet.get_worksheet(i).update("B1", upload_formated_data)
        else:
            sheet.get_worksheet(i).update(upload_formated_data)

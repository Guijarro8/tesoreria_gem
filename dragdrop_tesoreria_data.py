import streamlit as st
import json
import pandas as pd
import gspread

# Define the path to the existing file to be replaced
existing_file_path = "data/datos_tesoreria_gem.xlsx"

# Streamlit app
st.title("Drag & Drop Excel  de Tesorería GEM ")

uploaded_file = st.file_uploader("Upload an Excel file", type=["xls"])

credentials = json.loads(st.secrets["gcp_credentials"])

gc = gspread.service_account_from_dict(credentials)

sheet = gc.open_by_key(st.secrets["tesoreria_gem_key"])


if uploaded_file is not None:
    # Display the uploaded file name
    st.write(f"Uploaded file: {uploaded_file.name}")

    # Confirm replacement
    if st.button("Replace Existing File"):
        # Read the Excel file and save it as a CSV
        data = pd.read_excel(uploaded_file, skiprows=8)

        # Formato y limpieza de datos
        data = data.rename(
            columns={
                "F. Operativa": "fecha",
                "Concepto": "concepto",
                "Importe": "importe",
                "Saldo": "saldo",
            }
        )
        data = data[["fecha", "concepto", "importe", "saldo"]]
        data["fecha"] = pd.to_datetime(data["fecha"], format="%d/%m/%Y")
        data["mes_anio"] = data["fecha"].dt.to_period("M").astype(str)
        data["tipo"] = data["importe"].apply(
            lambda x: "cuota" if x in [15, 30, 60] else ("gasto" if x < 0 else "varios")
        )

        # tratamiento de concepto
        for word in ["ABONO", "TRANSFERENCIA", "RECIBO", "PAGO"]:
            data["concepto"] = (
                data["concepto"].str.replace(word, "", case=False).str.strip()
            )
        data["concepto"] = data["concepto"].apply(
            lambda x: x[3:] if x.startswith("DE ") else x
        )
        data["concepto"] = data["concepto"].str.lower()

        df_to_upload = {}
        df_to_upload["general"] = data.copy()
        # agrupación cuotas
        grouped_data = (
            data[data["tipo"] == "cuota"]
            .groupby(["concepto", "mes_anio"])
            .agg(importe_sum=("importe", "sum"))
            .reset_index()
        )

        # pivot para generar el formato que queremos
        pivot_table = grouped_data.pivot(
            index="concepto", columns="mes_anio", values="importe_sum"
        ).reset_index()

        # El importe total pagado
        pivot_table["importe pagado total"] = pivot_table.iloc[:, 1:].sum(
            axis=1, skipna=True
        )

        # conteo de null para obtener el número de cuotas pagadas
        pivot_table["numero cuotas pagadas"] = (
            pivot_table.shape[1] - pivot_table.iloc[:, 1:].isna().sum(axis=1) - 2
        )
        df_to_upload["cuotas"] = pivot_table[
            ["concepto"]
            + [col for col in list(pivot_table.columns)[::-1] if col != "concepto"]
        ]

        # división de los datos
        for data_type in ["gasto", "varios"]:
            df_to_upload[data_type] = data[data["tipo"] == data_type].drop(
                columns="saldo"
            )

        data_types = ["cuotas", "general", "gasto", "varios"]
        for i in range(len(data_types)):
            # llenar nulos con vacio
            df_to_upload[data_types[i]] = df_to_upload[data_types[i]].fillna("-")
            # borrar formato fecha
            if data_types[i] != "cuotas":
                df_to_upload[data_types[i]]["fecha"] = df_to_upload[data_types[i]][
                    "fecha"
                ].astype(str)

            # Formatear y subir a google sheets
            upload_formated_data = [
                df_to_upload[data_types[i]].columns.tolist()
            ] + df_to_upload[data_types[i]].values.tolist()

            if data_types[i] == "cuotas":
                sheet.get_worksheet(i + 1).update("B1", upload_formated_data)
            else:
                sheet.get_worksheet(i + 1).update(upload_formated_data)

        st.success(
            "The existing file has been successfully replaced! https://docs.google.com/spreadsheets/d/1S_lDqsjC0cuyJF2a0BcRB-eW5RXaLo_tlosoNS9IJvM/edit?gid=0#gid=0"
        )

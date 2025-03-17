import streamlit as st
import json
import pandas as pd
import gspread

# Define the path to the existing file to be replaced
existing_file_path = "data/datos_tesoreria_gem.xlsx"

# Streamlit app
st.title("Drag & Drop Excel  de Tesorería GEM ") 

uploaded_file = st.file_uploader("Upload an Excel file", type=["xls"])

credentials = json.loads(st.secrets['gcp_credentials'])

gc = gspread.service_account_from_dict(credentials)

sheet = gc.open_by_key(st.secrets['tesoreria_gem_key'])



if uploaded_file is not None:
    # Display the uploaded file name
    st.write(f"Uploaded file: {uploaded_file.name}")
    
    # Confirm replacement
    if st.button("Replace Existing File"):
        try:

            # Read the Excel file and save it as a CSV
            data = pd.read_excel(uploaded_file)
            data = pd.read_excel(uploaded_file, skiprows=8)

            #Formato y limpieza de datos
            data=data.rename(columns={'F. Operativa':'fecha',"Concepto":"concepto","Importe":"importe","Saldo":"saldo"})
            data=data[['fecha','concepto','importe','saldo']]
            data['fecha']=pd.to_datetime(data['fecha'],format='%d/%m/%Y')
            data['mes_anio'] = data['fecha'].dt.to_period('M').astype(str)
            data['tipo'] = data['importe'].apply(lambda x: 'cuota' if x in [15, 30, 60] else ('gasto' if x < 0 else 'varios'))

            #tratamiento de concepto
            for word in ['ABONO','TRANSFERENCIA','RECIBO','PAGO']:
                data['concepto'] = data['concepto'].str.replace(word, '', case=False).str.strip()
            data['concepto'] = data['concepto'].apply(lambda x: x[3:] if x.startswith('DE ') else x)
            data['concepto'] = data['concepto'].str.lower()

            #división de los datos
            #data_types = ['cuota', 'gasto', 'varios']
            # for data_type in data_types:
            #     globals()[f"data_{data_type}s"] = data[data['tipo'] == data_type].drop(columns='saldo')

            data_cuotas = data[data['tipo'] == 'cuotas'].drop(columns='saldo')
            data_general = data

            #agrupación cuotas
            cuotas = data_cuotas.groupby('concepto').agg({'importe': ['count', 'sum']}).reset_index()
            cuotas.columns = ['personas', 'numero_cuotas', 'importe_total']

            # Convert the dataframe 'cuotas' to a list of lists including the header
            data_types = ['cuotas', 'data_general']

            for i in range(len(data_types)):
                try:
                    globals()[f"{data_types[i]}"]['fecha'] = globals()[f"{data_types[i]}"]['fecha'].astype(str)
                except:
                    pass
                
                upload_data = [globals()[f"{data_types[i]}"].columns.tolist()] + globals()[f"{data_types[i]}"].values.tolist()
                sheet.get_worksheet(i+1).update(upload_data)

            st.success("The existing file has been successfully replaced! https://docs.google.com/spreadsheets/d/1S_lDqsjC0cuyJF2a0BcRB-eW5RXaLo_tlosoNS9IJvM/edit?gid=0#gid=0")
        except Exception as e:
            st.error(f"An error occurred: {e}")
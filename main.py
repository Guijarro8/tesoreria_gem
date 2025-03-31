import streamlit as st
import json
import gspread

from drag_drop import utils

# Define the path to the existing file to be replaced
existing_file_path = "data/datos_tesoreria_gem.xlsx"

# Streamlit app
st.title("Drag & Drop Excel de Tesorería GEM ")

uploaded_file = st.file_uploader("Upload an Excel file", type=["xls"])

if uploaded_file is not None:
    # Display the uploaded file name
    st.write(f"Uploaded file: {uploaded_file.name}")
    dfs_to_upload = utils.process_file(uploaded_file)

    # Confirm replacement
    if st.button("Replace Existing File"):
        credentials = json.loads(st.secrets["gcp_credentials"])
        tesoreria_gem_key = st.secrets["tesoreria_gem_key"]

        gc = gspread.service_account_from_dict(credentials)
        sheet = gc.open_by_key(tesoreria_gem_key)

        utils.upload_dataframes(dfs_to_upload, sheet)

        st.success(
            f"The existing file has been successfully replaced! https://docs.google.com/spreadsheets/d/{tesoreria_gem_key}/edit?gid=0#gid=0"
        )

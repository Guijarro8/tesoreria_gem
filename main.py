import json
from typing import Any, cast

import gspread
import streamlit as st

from drag_drop import utils


def main() -> None:
    """Render the Streamlit application."""
    st.title("Drag & Drop Excel de Tesorería GEM")

    uploaded_file = st.file_uploader("Upload an Excel file", type=["xls"])

    if uploaded_file is None:
        return

    st.write(f"Uploaded file: {uploaded_file.name}")
    dataframes = utils.process_file(uploaded_file)

    if st.button("Replace Existing File"):
        credentials = cast(
            dict[str, Any],
            json.loads(st.secrets["gcp_credentials"]),
        )
        tesoreria_gem_key = st.secrets["tesoreria_gem_key"]

        gc = gspread.service_account_from_dict(credentials)
        spreadsheet = gc.open_by_key(tesoreria_gem_key)

        utils.upload_dataframes(dataframes, spreadsheet)

        st.success(
            "The existing file has been successfully replaced! "
            "https://docs.google.com/spreadsheets/d/"
            f"{tesoreria_gem_key}/edit?gid=0#gid=0"
        )


if __name__ == "__main__":
    main()

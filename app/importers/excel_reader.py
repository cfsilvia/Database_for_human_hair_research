from pathlib import Path
from typing import Any
import pandas as pd

'''Read an Excel file and return its contents as a DataFrame and metadata.'''

def read_excel_file(file_path: str | Path, sheet_name: str | int = 0,) -> tuple[pd.DataFrame, dict[str, Any]]:
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"The file {file_path} does not exist.")
    with pd.ExcelFile(file_path) as excel_file:
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
        sheet_names = excel_file.sheet_names

    # Remove whitespace from column names
    df.columns = [
        str(column).strip()
        for column in df.columns
    ]

    metadata = {
        "filename": file_path.name,
        "sheet_names": sheet_names,
        "selected_sheet": sheet_name,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": df.columns.tolist(),
    }

    return df, metadata

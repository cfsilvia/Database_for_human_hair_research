from pathlib import Path
from typing import Any
import re

import pandas as pd
import openpyxl

def extract_question_number(value):
    """
    Extract Q number from a cell.

    Examples:
        Q12. Medication  -> Q12
        q12.1 something -> Q12.1
        Subject ID      -> None
    """

    if not isinstance(value, str):
        return None

    match = re.match(
        r"^(Q\d+(?:\.\d+)?)",
        value.strip(),
        flags=re.IGNORECASE,
    )

    if match:
        return match.group(1).upper()

    return None

'''
Correct headers
'''
def classify_followup(sub_value):
    """
    Convert non-numbered second-row fields
    to the convention used in question_metadata.xlsx.

    Examples:
        אחר, אנא פרט   -> other
        אם כן, אנא פרט -> detail
    """

    if not isinstance(sub_value, str):
        return None

    text = sub_value.strip()

    # "Other, please specify"
    if "אחר" in text and "פרט" in text:
        return "other"

    # Additional detail / free-text follow-up
    if "אם כן" in text:
        return "detail"

    if "תוספי תזונה" in text:
        return "detail"

    return None


def build_questionnaire_headers(
    worksheet,
    main_header_row=1,
    subheader_row=2,
):
    headers = []

    current_main_question = None

    for col in range(1,worksheet.max_column + 1,):
        main_value = worksheet.cell(main_header_row,col,).value
        sub_value = worksheet.cell(subheader_row,col,).value

        main_q = extract_question_number(main_value)

        sub_q = extract_question_number(sub_value)

        # ------------------------------------
        # A new main question starts
        # ------------------------------------
        if main_q is not None:
            current_main_question = main_q

        # ------------------------------------
        # Numbered subquestion
        #
        # Q12 parent
        # Q12.1 second header
        #
        # Result -> Q12.1
        # ------------------------------------
        if sub_q is not None:
            headers.append(sub_q)
            continue

        # ------------------------------------
        # Main answer
        #
        # Q5 + Answer
        #
        # Result -> Q5
        # ------------------------------------
        if (
            current_main_question is not None
            and isinstance(sub_value, str)
            and sub_value.strip().lower() == "answer"
        ):
            headers.append(current_main_question)
            continue

        # ------------------------------------
        # .other or .detail
        # ------------------------------------
        suffix = classify_followup(sub_value)

        if (current_main_question is not None
            and suffix is not None):
            headers.append(f"{current_main_question}.{suffix}")
            continue

        # ------------------------------------
        # Ordinary question without
        # a special second header
        # ------------------------------------
        if main_q is not None:
            headers.append(main_q)
            continue

        # ------------------------------------
        # Administrative field
        # Subject ID, Started, Ended, etc.
        # ------------------------------------
        if main_value is not None:
            headers.append(str(main_value).strip().lower())

            # Administrative column means
            # we are no longer inside a Q group
            current_main_question = None

            continue

        # ------------------------------------
        # Unrecognized column
        # ------------------------------------
        headers.append(f"column_{col}")

    return headers




'''
add questionarie reader
'''



def read_questionnaire_file(
    file_path,
    sheet_name=0,
):
    workbook = openpyxl.load_workbook(
        file_path,
        data_only=True,
    )

    if isinstance(sheet_name, int):
        worksheet = workbook.worksheets[
            sheet_name
        ]
    else:
        worksheet = workbook[
            sheet_name
        ]

    headers = build_questionnaire_headers(
        worksheet
    )

    data = worksheet.iter_rows(
        min_row=3,
        values_only=True,
    )

    df = pd.DataFrame(
        data,
        columns=headers,
    )
    
    # Remove completely empty rows
    df = df.dropna(
        how="all"
    ).reset_index(drop=True)

    return df


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

"""
    Load an Excel file and return it as a pandas DataFrame
"""
def get_excel_file(file_path: str) -> pd.DataFrame:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() not in {".xlsx", ".xls"}:
        raise ValueError("File must be an Excel file (.xlsx or .xls)")

    df = pd.read_excel(path)

    return df
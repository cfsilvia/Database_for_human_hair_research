import re
from pathlib import Path

import pandas as pd


DEFAULT_VALIDATION_REPORT_PATH = Path("data/validation_results.xlsx")
EXCEL_HEADER_ROWS_READ_BY_PANDAS = 1
ROWS_BEFORE_DATA = 3


class ValidationError(Exception):
    """Raised when an imported questionnaire is not valid."""


# Input: 1-based Excel column number.
# Output: Excel column letters, such as A, Z, or AA.
def excel_column_letter(column_number: int) -> str:
    """Return Excel column letters for a 1-based column number."""
    letters = ""

    while column_number:
        column_number, remainder = divmod(column_number - 1, 26)
        letters = chr(65 + remainder) + letters

    return letters


# Input: pandas DataFrame row index and the number of Excel header rows read by pandas.
# Output: matching 1-based Excel worksheet row number.
def dataframe_index_to_excel_row(
    dataframe_index: int,
    excel_header_rows_read_by_pandas: int = EXCEL_HEADER_ROWS_READ_BY_PANDAS,
) -> int:
    """Convert a pandas DataFrame index to the matching Excel worksheet row."""
    return int(dataframe_index) + excel_header_rows_read_by_pandas + 1


# Input: DataFrame and column name.
# Output: 1-based position of the column in the DataFrame.
def get_column_number(df: pd.DataFrame, column_name: str) -> int:
    return df.columns.tolist().index(column_name) + 1


# Input: DataFrame, DataFrame row index, column name, and header-row offset.
# Output: Excel cell reference, row number, and column letter for that DataFrame value.
def get_excel_cell(
    df: pd.DataFrame,
    dataframe_index: int,
    column_name: str,
    excel_header_rows_read_by_pandas: int = EXCEL_HEADER_ROWS_READ_BY_PANDAS,
) -> tuple[str, int, str]:
    column_number = get_column_number(df, column_name)
    column_letter = excel_column_letter(column_number)
    excel_row = dataframe_index_to_excel_row(
        dataframe_index,
        excel_header_rows_read_by_pandas,
    )

    return f"{column_letter}{excel_row}", excel_row, column_letter


# Input: DataFrame and column name.
# Output: Excel header cell reference, row number, and column letter.
def get_header_excel_cell(df: pd.DataFrame, column_name: str) -> tuple[str, int, str]:
    column_number = get_column_number(df, column_name)
    column_letter = excel_column_letter(column_number)

    return f"{column_letter}1", 1, column_letter


# Input: validation name, message, Excel location details, column/value details, and optional filename.
# Output: dictionary describing one validation problem.
def make_problem(
    validation: str,
    message: str,
    excel_cell: str | None,
    excel_row: int | None,
    excel_column: str | None,
    column_name: str | None,
    value: object,
    filename: str | Path | None = None,
) -> dict:
    return {
        "filename": None if filename is None else Path(filename).name,
        "validation": validation,
        "message": message,
        "excel_cell": excel_cell,
        "excel_row": excel_row,
        "excel_column": excel_column,
        "column_name": column_name,
        "value": value,
    }


# Input: question column name and question prefix, such as Q.
# Output: Hebrew text extracted from the question column name.
def get_question_hebrew_text(column: object, question_prefix: str) -> str:
    column_name = str(column)
    question_text = re.sub(
        rf"^{re.escape(question_prefix)}\s*\d+\s*[.]?\s*",
        "",
        column_name,
    )

    return " ".join(re.findall(r"[\u0590-\u05FF]+", question_text))


# Input: DataFrame and question column prefix.
# Output: DataFrame listing question columns with duplicated Hebrew text.
def find_similar_question_columns(
    df: pd.DataFrame,
    question_prefix: str = "Q",
) -> pd.DataFrame:
    question_columns = [col for col in df.columns if str(col).startswith(question_prefix)]
    first_column_by_text = {}
    similar_questions = []

    for column in question_columns:
        hebrew_text = get_question_hebrew_text(column, question_prefix)

        if not hebrew_text:
            continue

        if hebrew_text in first_column_by_text:
            similar_questions.append(
                {
                    "hebrew_text": hebrew_text,
                    "first_question_column": first_column_by_text[hebrew_text],
                    "similar_question_column": column,
                }
            )
        else:
            first_column_by_text[hebrew_text] = column
    summary_df = pd.DataFrame(similar_questions, columns=["hebrew_text", "first_question_column", "similar_question_column"])
    return summary_df

# Input: DataFrame and question column prefix.
# Output: None when question columns are unique; raises ValidationError when duplicates exist.
# Check that question column names are unique.
def validate_question_columns_unique(df: pd.DataFrame, question_prefix: str = "Q",) -> None:
    similar_questions = find_similar_question_columns(df, question_prefix)

    if not similar_questions.empty:
        raise ValidationError(
            "Duplicated question columns found:\n"
            f"{similar_questions.to_string(index=False)}"
        )


# Input: DataFrame and subject ID column name.
# Output: None when subject IDs are numeric; raises ValidationError when invalid values exist.
# Check that subject ID contains only numeric values.
def validate_subject_id_numeric(
    df: pd.DataFrame,
    subject_id_column: str = "subject ID",
) -> None:
   
    if subject_id_column not in df.columns:
        raise ValidationError(f"Column '{subject_id_column}' was not found.")

    converted = pd.to_numeric(df[subject_id_column], errors="coerce")
    invalid_mask = df[subject_id_column].notna() & converted.isna()

    if invalid_mask.any():
        invalid_rows = df.index[invalid_mask].tolist()
        raise ValidationError(
            f"subject ID contains non-numeric values in rows: {invalid_rows}"
        )


# Input: DataFrame and question column prefix.
# Output: first matching column name, or None when no column matches.
# Find and return the first column name that starts with the given prefix.
def find_question_column(df: pd.DataFrame, question_prefix: str = "Q1") -> str | None:
    
    for col in df.columns:
        if str(col).startswith(question_prefix):
            return col
    return None


# Input: DataFrame and subject ID column name.
# Output: None when subject ID matches Q1; raises ValidationError when mismatches exist.
# Check that subject ID equals Q1 for every row where both are numeric.
def validate_subject_id_matches_q1(
    df: pd.DataFrame,
    subject_id_column: str = "subject ID",
) -> None:
    
    if subject_id_column not in df.columns:
        raise ValidationError(f"Column '{subject_id_column}' was not found.")

    q1_column = find_question_column(df, "Q1")
    if q1_column is None:
        raise ValidationError("Column starting with 'Q1' was not found.")

    subject_id = pd.to_numeric(df[subject_id_column], errors="coerce")
    q1 = pd.to_numeric(df[q1_column], errors="coerce")

    valid = subject_id.notna() & q1.notna()
    mismatch = valid & (subject_id != q1)

    if mismatch.any():
        bad_rows = df.loc[mismatch, [subject_id_column, q1_column]]
        raise ValidationError("Subject ID does not match Q1:\n" f"{bad_rows}")


# Input: DataFrame with a Q1 question column.
# Output: DataFrame containing rows where Q1 has non-numeric values.
# Find rows where Q1 contains a value that is not numeric.
def find_non_numeric_q1_rows(df: pd.DataFrame) -> pd.DataFrame:
    
    q1_column = find_question_column(df, "Q1")
    if q1_column is None:
        raise ValidationError("Column starting with 'Q1' was not found.")

    numeric_q1 = pd.to_numeric(df[q1_column], errors="coerce")
    invalid_mask = df[q1_column].notna() & numeric_q1.isna()
    invalid_values = df.loc[invalid_mask, [q1_column]]
    return invalid_values


# Input: DataFrame with a Q1 question column.
# Output: None when Q1 is numeric; raises ValidationError when non-numeric values exist.
# Check that Q1 contains only numeric values.
def validate_q1_numeric(df: pd.DataFrame) -> None:
   
    invalid_rows = find_non_numeric_q1_rows(df)

    if not invalid_rows.empty:
        raise ValidationError("Q1 contains non-numeric values:\n" f"{invalid_rows}")


# Input: number of rows before data and number of Excel header rows read by pandas.
# Output: first DataFrame index that contains imported data.
def get_first_data_dataframe_index(
    rows_before_data: int = ROWS_BEFORE_DATA,
    excel_header_rows_read_by_pandas: int = EXCEL_HEADER_ROWS_READ_BY_PANDAS,
) -> int:
    return max(rows_before_data - excel_header_rows_read_by_pandas, 0)


# Input: DataFrame, number of rows before data, and optional filename.
# Output: list of validation problem dictionaries.
def find_validation_problems(
    df: pd.DataFrame,
    rows_before_data: int = ROWS_BEFORE_DATA,
    filename: str | Path | None = None,
) -> list[dict]:
    problems = []
    first_data_index = get_first_data_dataframe_index(rows_before_data)
    data_df = df.iloc[first_data_index:]

    similar_questions = find_similar_question_columns(df)
    for _, row in similar_questions.iterrows():
        message = f"Duplicated question text: {row['hebrew_text']}"

        for column_key in ("first_question_column", "similar_question_column"):
            column_name = row[column_key]
            excel_cell, excel_row, excel_column = get_header_excel_cell(df, column_name)
            problems.append(
                make_problem(
                    "validate_question_columns_unique",
                    message,
                    excel_cell,
                    excel_row,
                    excel_column,
                    column_name,
                    column_name,
                    filename,
                )
            )

    subject_id_column = "subject ID"
    if subject_id_column not in df.columns:
        problems.append(
            make_problem(
                "validate_subject_id_numeric",
                f"Column '{subject_id_column}' was not found.",
                None,
                None,
                None,
                subject_id_column,
                None,
                filename,
            )
        )
    else:
        subject_id = pd.to_numeric(data_df[subject_id_column], errors="coerce")
        invalid_subject_id = data_df[subject_id_column].notna() & subject_id.isna()

        for dataframe_index, value in data_df.loc[invalid_subject_id, subject_id_column].items():
            excel_cell, excel_row, excel_column = get_excel_cell(
                df,
                dataframe_index,
                subject_id_column,
            )
            problems.append(
                make_problem(
                    "validate_subject_id_numeric",
                    "subject ID contains a non-numeric value.",
                    excel_cell,
                    excel_row,
                    excel_column,
                    subject_id_column,
                    value,
                    filename,
                )
            )

    q1_column = find_question_column(df, "Q1")
    if q1_column is None:
        problems.append(
            make_problem(
                "validate_q1_numeric",
                "Column starting with 'Q1' was not found.",
                None,
                None,
                None,
                None,
                None,
                filename,
            )
        )
    else:
        q1 = pd.to_numeric(data_df[q1_column], errors="coerce")
        invalid_q1 = data_df[q1_column].notna() & q1.isna()

        for dataframe_index, value in data_df.loc[invalid_q1, q1_column].items():
            excel_cell, excel_row, excel_column = get_excel_cell(df, dataframe_index, q1_column)
            problems.append(
                make_problem(
                    "validate_q1_numeric",
                    "Q1 contains a non-numeric value.",
                    excel_cell,
                    excel_row,
                    excel_column,
                    q1_column,
                    value,
                    filename,
                )
            )

    if subject_id_column in df.columns and q1_column is not None:
        subject_id = pd.to_numeric(data_df[subject_id_column], errors="coerce")
        q1 = pd.to_numeric(data_df[q1_column], errors="coerce")
        mismatch = subject_id.notna() & q1.notna() & (subject_id != q1)

        for dataframe_index in data_df.index[mismatch]:
            for column_name in (subject_id_column, q1_column):
                excel_cell, excel_row, excel_column = get_excel_cell(df, dataframe_index, column_name)
                problems.append(
                    make_problem(
                        "validate_subject_id_matches_q1",
                        "Subject ID does not match Q1.",
                        excel_cell,
                        excel_row,
                        excel_column,
                        column_name,
                        df.at[dataframe_index, column_name],
                        filename,
                    )
                )

    return problems


# Input: validation problem dictionaries and output Excel path.
# Output: path where the validation report was saved.
def save_validation_report(problems: list[dict], output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "filename",
        "validation",
        "message",
        "excel_cell",
        "excel_row",
        "excel_column",
        "column_name",
        "value",
    ]
    pd.DataFrame(problems, columns=columns).to_excel(output_path, index=False)

    return output_path


# Input: DataFrame, optional report output path, data-row offset, and optional filename.
# Output: dictionary with validation results and report details.
# Run all current validations and return a report.
def validate_import(
    df: pd.DataFrame,
    output_path: str | Path | None = DEFAULT_VALIDATION_REPORT_PATH,
    rows_before_data: int = ROWS_BEFORE_DATA,
    filename: str | Path | None = None,
) -> dict:
    
    results = {}

    validators = (
        validate_question_columns_unique,
        validate_subject_id_numeric,
        validate_subject_id_matches_q1,
        validate_q1_numeric,
    )

    for validator in validators:
        try:
            validator(df)
        except ValidationError as error:
            results[validator.__name__] = {
                "valid": False,
                "error": str(error),
            }
        else:
            results[validator.__name__] = {
                "valid": True,
                "error": None,
            }

    try:
        non_numeric_q1_rows = find_non_numeric_q1_rows(df)
    except ValidationError as error:
        results["find_non_numeric_q1_rows"] = {
            "valid": False,
            "error": str(error),
            "rows": None,
        }
    else:
        results["find_non_numeric_q1_rows"] = {
            "valid": non_numeric_q1_rows.empty,
            "error": None if non_numeric_q1_rows.empty else "Q1 contains non-numeric values.",
            "rows": non_numeric_q1_rows.to_dict(orient="records"),
        }

    problems = find_validation_problems(
        df,
        rows_before_data=rows_before_data,
        filename=filename,
    )
    report_path = None

    if output_path is not None:
        report_path = save_validation_report(problems, output_path)

    results["validation_report"] = {
        "valid": len(problems) == 0,
        "error": None if len(problems) == 0 else "Validation problems were found.",
        "problem_count": len(problems),
        "filename": None if filename is None else Path(filename).name,
        "path": None if report_path is None else str(report_path),
        "problems": problems,
    }

    return results

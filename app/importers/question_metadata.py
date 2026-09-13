from pathlib import Path
import re

import openpyxl
import pandas as pd


PURPLE = "FF7030A0"


# Input: openpyxl worksheet.
# Output: row number of the first questionnaire header row, or None if not found.
def find_header_row(ws):
    for row in range(1, min(ws.max_row, 10) + 1):
        for col in range(1, ws.max_column + 1):
            value = ws.cell(row, col).value

            if isinstance(value, str) and re.match(r"^Q\d+", value):
                return row

    return None


# Input: question header text from Excel.
# Output: question number and Hebrew phrase, or (None, None) if the header is not a question.
def split_question(header):
    match = re.match(
        r"^(Q\d+)[\.\s:-]*(.*)$",
        str(header).strip(),
        flags=re.DOTALL,
    )

    if not match:
        return None, None

    return match.group(1), match.group(2).strip()


# Input: openpyxl cell from a question header.
# Output: questionnaire type based on font color.
def get_questionnaire_type(cell):
    color = cell.font.color

    if color is not None and color.type == "rgb":
        if color.rgb == PURPLE:
            return "second-questionnaire"

    return "first-questionnaire"


# Input: Excel sheet name.
# Output: gender form value, either male or female.
def get_gender_form(sheet_name):
    name = sheet_name.strip().lower()

    if name == "men":
        return "male"

    if name == "women":
        return "female"

    raise ValueError(f"Unknown sheet name: {sheet_name}")


# Input: Excel file path.
# Output: cleaned file name without date/number prefixes.
def clean_file_name(file_path):
    name = Path(file_path).stem

    name = re.sub(
        r"^\d+[.\-_]\d+[.\-_]\d+[.\-_]?",
        "",
        name,
    )

    name = re.sub(r"\d+", "", name)

    return name.strip("._- ")


# Input: wanted Excel sheet name and sheet names already used in the workbook.
# Output: valid unique Excel sheet name.
def make_sheet_name(name, used_names):
    sheet_name = re.sub(r"[\\/*?:\[\]]", "_", str(name)).strip()
    sheet_name = sheet_name[:31] or "questions"

    original_sheet_name = sheet_name
    counter = 2

    while sheet_name in used_names:
        suffix = f"_{counter}"
        sheet_name = f"{original_sheet_name[:31 - len(suffix)]}{suffix}"
        counter += 1

    used_names.add(sheet_name)
    return sheet_name


# Input: openpyxl worksheet and cleaned source file name.
# Output: list of question metadata records from that worksheet.
def read_questions_from_sheet(ws, file_name):
    header_row = find_header_row(ws)
    subheader_row = header_row + 1

    if header_row is None:
        return []

    gender_form = get_gender_form(ws.title)

    records = []
    current_main_question = None
    current_main_phrase = None

    for col in range(1, ws.max_column + 1):
        header_cell = ws.cell(header_row, col)
        subheader_cell = ws.cell(subheader_row, col)

        header = header_cell.value
        subheader = subheader_cell.value

        # If there is a main question in row 2,
        # remember it for following columns
        if isinstance(header, str):
            q_number, q_phrase = split_question(header)

            if q_number is not None:
                current_main_question = q_number
                current_main_phrase = q_phrase

        # Ignore columns that are not part of a question
        if current_main_question is None:
            continue

        subquestion_number = None
        subquestion_phrase = None

        if isinstance(subheader, str):
            subquestion_number, subquestion_phrase = split_question(
                subheader
            )

            # "Answer" has no Q-number
            if subquestion_number is None:
                subquestion_phrase = subheader.strip()

             # Only create a record if this column actually
             # belongs to a questionnaire question
            if header is None and subheader is None:
              continue




        records.append(
            {
                "number question": current_main_question,
                "question": current_main_phrase,
                "subquestion number": subquestion_number,
                "subquestion": subquestion_phrase,
                "questionnaire":
                    get_questionnaire_type(header_cell),
                "file name": file_name,
                "gender_form": gender_form,
            }
        )

    return records


# Input: Excel file path.
# Output: list of question metadata records from men and women sheets.
def read_questions_from_file(file_path):
    workbook = openpyxl.load_workbook(
        file_path,
        data_only=False,
    )

    file_name = clean_file_name(file_path)

    records = []

    for gender in ["men", "women"]:
        for ws in workbook.worksheets:
            if ws.title.strip().lower() == gender:
                records.extend(
                    read_questions_from_sheet(
                        ws,
                        file_name,
                    )
                )

    return records


# Input: folder containing questionnaire Excel files and optional output file name.
# Output: DataFrame with question metadata, optionally saved to Excel with one sheet per file.
def build_question_metadata(
    data_folder="data",
    output_file=None,
):
    data_folder = Path(data_folder)

    records = []
    sheets = []

    for file_path in data_folder.glob("*.xlsx"):
        if output_file is not None:
            if file_path.name == Path(output_file).name:
                continue

        file_records = read_questions_from_file(file_path)
        records.extend(file_records)
        sheets.append((clean_file_name(file_path), pd.DataFrame(file_records)))

    df = pd.DataFrame(records)

    if output_file is not None:
        output_path = data_folder / output_file
        used_names = set()

        with pd.ExcelWriter(output_path) as writer:
            if not sheets:
                df.to_excel(writer, sheet_name="questions", index=False)
            else:
                for sheet_name, sheet_df in sheets:
                    sheet_df.to_excel(
                        writer,
                        sheet_name=make_sheet_name(sheet_name, used_names),
                        index=False,
                    )

    return df

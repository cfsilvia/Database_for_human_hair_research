"""Generate the displayed participants table without querying the database."""

from datetime import date
from io import BytesIO

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import IllegalCharacterError
from pydantic import BaseModel, Field


router = APIRouter()


class ExportColumn(BaseModel):
    key: str
    label: str
    parent_question: str | None = None
    question: str | None = None


class ExportGroup(BaseModel):
    test: str
    columns: list[ExportColumn] = Field(min_length=1)


class ParticipantsTableExport(BaseModel):
    fixed_columns: list[ExportColumn]
    groups: list[ExportGroup]
    rows: list[dict[str, str | int | float | bool | None]] = Field(min_length=1)
    filter_description: str = "None"
    save_date: date


def build_participants_workbook(table: ParticipantsTableExport) -> bytes:
    columns = [ExportColumn(key="subject_id", label="participant/subject_id")]
    columns.extend(table.fixed_columns)
    for group in table.groups:
        columns.extend(group.columns)

    if len(columns) > 16384 or len(table.rows) > 1048571:
        raise ValueError("The displayed table exceeds Excel's worksheet size limit.")

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Participants"

    def write_cell(row, column, value):
        cell = sheet.cell(row=row, column=column, value=value)
        # Questionnaire text beginning with '=' must remain text, never a formula.
        if isinstance(value, str):
            cell.data_type = "s"
        return cell

    write_cell(1, 1, "Participants table").font = Font(bold=True, size=16)
    write_cell(2, 1, f"Filters: {table.filter_description or 'None'}")
    sheet.cell(2, 1).alignment = Alignment(wrap_text=True, vertical="top")
    if len(columns) > 1:
        sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(columns))
        sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(columns))
    sheet.row_dimensions[2].height = 60

    for index, column in enumerate(columns[:1 + len(table.fixed_columns)], start=1):
        write_cell(4, index, column.label)
        sheet.merge_cells(start_row=4, start_column=index, end_row=5, end_column=index)

    index = 2 + len(table.fixed_columns)
    for group in table.groups:
        write_cell(4, index, group.test)
        if len(group.columns) > 1:
            sheet.merge_cells(
                start_row=4, start_column=index,
                end_row=4, end_column=index + len(group.columns) - 1,
            )
        for column in group.columns:
            heading = "\n\n".join(
                text for text in (column.parent_question, column.question or column.label)
                if text
            )
            write_cell(5, index, heading)
            index += 1

    for row in sheet.iter_rows(min_row=4, max_row=5, max_col=len(columns)):
        for cell in row:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="E8EEF2")
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    sheet.row_dimensions[5].height = 90
    for index in range(1, len(columns) + 1):
        sheet.column_dimensions[get_column_letter(index)].width = 28 if index > 1 else 22

    for row_index, row in enumerate(table.rows, start=6):
        for column_index, column in enumerate(columns, start=1):
            write_cell(row_index, column_index, row.get(column.key))

    sheet.freeze_panes = "B6"
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()

#Sends the table to the server
@router.post("/api/participants-table/export")
def export_participants_table(table: ParticipantsTableExport):
    try:
        content = build_participants_workbook(table)
    except (ValueError, IllegalCharacterError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    filename = f"participants_table_{table.save_date.isoformat()}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

import unittest
from io import BytesIO

from fastapi import HTTPException
from openpyxl import load_workbook
from pydantic import ValidationError

from app.participants_export import (
    ParticipantsTableExport,
    build_participants_workbook,
    export_participants_table,
)


class ParticipantsExportTests(unittest.TestCase):
    def make_table(self, **changes):
        data = {
            "fixed_columns": [{"key": "answered", "label": "Answered questionnaire 1"}],
            "groups": [{"test": "Test A", "columns": [
                {"key": "answer", "label": "שאלה", "parent_question": "כותרת",
                 "question": "שאלה\nנוספת"},
                {"key": "blank", "label": "Empty"},
            ]}],
            "rows": [{"subject_id": 12, "answered": "Yes", "answer": 0, "blank": ""}],
            "filter_description": "Subject ID contains: 12; Show test: Test A",
            "save_date": "2026-10-28",
        }
        data.update(changes)
        return ParticipantsTableExport.model_validate(data)

    def read_sheet(self, table):
        return load_workbook(BytesIO(build_participants_workbook(table))).active

    def test_titles_grouped_headers_and_hebrew(self):
        sheet = self.read_sheet(self.make_table())
        self.assertEqual(sheet["A1"].value, "Participants table")
        self.assertEqual(sheet["A2"].value,
                         "Filters: Subject ID contains: 12; Show test: Test A")
        self.assertEqual(sheet["A4"].value, "participant/subject_id")
        self.assertEqual(sheet["C4"].value, "Test A")
        self.assertEqual(sheet["C5"].value, "כותרת\n\nשאלה\nנוספת")
        self.assertIn("C4:D4", {str(cells) for cells in sheet.merged_cells.ranges})
        self.assertEqual(sheet.freeze_panes, "B6")

    def test_exports_only_supplied_rows_and_columns_in_order(self):
        table = self.make_table(rows=[
            {"subject_id": 23, "answered": "No", "answer": "שלום", "extra": "hidden"},
            {"subject_id": 12, "answered": "Yes", "answer": 0},
        ])
        sheet = self.read_sheet(table)
        self.assertEqual(sheet.max_column, 4)
        self.assertEqual(sheet.max_row, 7)
        self.assertEqual([cell.value for cell in sheet[6]], [23, "No", "שלום", None])
        self.assertEqual([cell.value for cell in sheet[7]], [12, "Yes", 0, None])

    def test_unfiltered_export_without_question_groups(self):
        sheet = self.read_sheet(self.make_table(
            fixed_columns=[], groups=[], filter_description="None",
            rows=[{"subject_id": 12}],
        ))
        self.assertEqual(sheet["A2"].value, "Filters: None")
        self.assertEqual(sheet["A6"].value, 12)
        self.assertEqual(sheet.max_column, 1)

    def test_formula_like_values_and_headings_remain_text(self):
        table = self.make_table(
            fixed_columns=[{"key": "text", "label": "=1+1"}], groups=[],
            rows=[{"subject_id": 12, "text": '=HYPERLINK("https://example.com")'}],
        )
        sheet = self.read_sheet(table)
        self.assertEqual(sheet["B4"].value, "=1+1")
        self.assertEqual(sheet["B4"].data_type, "s")
        self.assertEqual(sheet["B6"].data_type, "s")
        self.assertTrue(sheet["B6"].value.startswith("=HYPERLINK"))

    def test_response_uses_supplied_local_date(self):
        response = export_participants_table(self.make_table(save_date="2027-01-01"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-disposition"],
                         'attachment; filename="participants_table_2027-01-01.xlsx"')
        self.assertIn("spreadsheetml.sheet", response.headers["content-type"])
        self.assertEqual(load_workbook(BytesIO(response.body)).active["A1"].value,
                         "Participants table")

    def test_rejects_invalid_date_and_empty_rows(self):
        for changes in ({"save_date": "2026-02-30"}, {"rows": []}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.make_table(**changes)

    def test_invalid_excel_text_returns_readable_error(self):
        table = self.make_table(rows=[{"subject_id": 12, "answer": "bad\x00text"}])
        with self.assertRaises(HTTPException) as caught:
            export_participants_table(table)
        self.assertEqual(caught.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()

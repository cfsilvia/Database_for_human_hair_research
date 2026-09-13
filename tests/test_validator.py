import unittest
from tempfile import TemporaryDirectory

import pandas as pd

from app.importers.validator import (
    ValidationError,
    dataframe_index_to_excel_row,
    find_similar_question_columns,
    validate_import,
    validate_question_columns_unique,
)


class ValidateQuestionColumnsUniqueTests(unittest.TestCase):
    def test_finds_similar_questions_with_both_q_columns(self) -> None:
        df = pd.DataFrame(
            [["yes", "no"]],
            columns=["Q1. האם יש נשירה?", "Q2 האם יש נשירה"],
        )

        similar_questions = find_similar_question_columns(df)

        self.assertEqual(
            similar_questions.to_dict(orient="records"),
            [
                {
                    "hebrew_text": "האם יש נשירה",
                    "first_question_column": "Q1. האם יש נשירה?",
                    "similar_question_column": "Q2 האם יש נשירה",
                }
            ],
        )

    def test_compares_hebrew_text_only(self) -> None:
        df = pd.DataFrame(
            [["yes", "no"]],
            columns=["Q1. האם יש נשירה?", "Q2 האם יש נשירה"],
        )

        with self.assertRaisesRegex(ValidationError, "Q1. האם יש נשירה.*Q2 האם יש נשירה"):
            validate_question_columns_unique(df)

    def test_allows_different_hebrew_text(self) -> None:
        df = pd.DataFrame(
            [["yes", "no"]],
            columns=["Q1. האם יש נשירה?", "Q2 האם יש גרד"],
        )

        validate_question_columns_unique(df)


class ValidateImportReportTests(unittest.TestCase):
    def test_dataframe_index_maps_to_actual_excel_row(self) -> None:
        self.assertEqual(dataframe_index_to_excel_row(2), 4)

    def test_writes_report_with_actual_excel_cells(self) -> None:
        df = pd.DataFrame(
            [
                [None, None],
                [None, None],
                ["bad-id", "bad-q1"],
            ],
            columns=["subject ID", "Q1. patient id"],
        )

        with TemporaryDirectory() as temp_dir:
            output_path = f"{temp_dir}/validation_results.xlsx"

            results = validate_import(
                df,
                output_path=output_path,
                filename="questionnaire.xlsx",
            )
            report_df = pd.read_excel(output_path)

        self.assertFalse(results["validation_report"]["valid"])
        self.assertEqual(results["validation_report"]["problem_count"], 2)
        self.assertEqual(results["validation_report"]["filename"], "questionnaire.xlsx")
        self.assertEqual(report_df["filename"].tolist(), ["questionnaire.xlsx", "questionnaire.xlsx"])
        self.assertEqual(report_df["excel_cell"].tolist(), ["A4", "B4"])
        self.assertEqual(report_df["excel_row"].tolist(), [4, 4])


if __name__ == "__main__":
    unittest.main()

import unittest

import pandas as pd

from app.importers.subject_id_corrector import correct_subject_ids


class CorrectSubjectIdsTests(unittest.TestCase):
    def test_accepts_lowercase_subject_id_column(self) -> None:
        questionnaire_df = pd.DataFrame({"subject ID": [100, 200]})
        correction_df = pd.DataFrame(
            [[100, None, None, None, None, None, None, None, None, None, None, 101]],
            columns=[
                "Subject ID",
                "B",
                "C",
                "D",
                "E",
                "F",
                "G",
                "H",
                "I",
                "J",
                "K",
                "corrected ID",
            ],
        )

        corrected_df, n_corrected = correct_subject_ids(
            questionnaire_df,
            correction_df,
        )

        self.assertEqual(n_corrected, 1)
        self.assertEqual(corrected_df["subject ID"].tolist(), [101, 200])

    def test_handles_duplicate_subject_id_headers(self) -> None:
        questionnaire_df = pd.DataFrame(
            [[100, "ignored"], [200, "ignored"]],
            columns=["Subject ID", "Subject ID"],
        )
        correction_df = pd.DataFrame(
            [[100, None, None, None, None, None, None, None, None, None, None, 101]],
            columns=[
                "Subject ID",
                "B",
                "C",
                "D",
                "E",
                "F",
                "G",
                "H",
                "I",
                "J",
                "K",
                "corrected ID",
            ],
        )

        corrected_df, n_corrected = correct_subject_ids(
            questionnaire_df,
            correction_df,
        )

        self.assertEqual(n_corrected, 1)
        self.assertEqual(corrected_df.iloc[:, 0].tolist(), [101, 200])
        self.assertEqual(corrected_df.iloc[:, 1].tolist(), ["ignored", "ignored"])


if __name__ == "__main__":
    unittest.main()

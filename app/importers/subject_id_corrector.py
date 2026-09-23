import pandas as pd




"""
    Correct Subject ID values using column L of the correction file.

    Only non-empty values in column L are used.
    Empty values leave the original Subject ID unchanged.

    Returns
    -------
    corrected_df : pd.DataFrame
    n_corrected : int
"""
def correct_subject_ids(
    questionnaire_df: pd.DataFrame,
    correction_df: pd.DataFrame,
    subject_id_column: str = "subject ID",
    correction_column_index: int = 11,   # Excel column L
) -> pd.DataFrame:

    if len(questionnaire_df) != len(correction_df):
        raise ValueError("Questionnaire file and correction file "
                      "do not have the same number of rows."
        )

    df = questionnaire_df.copy()
    corrected_ids = correction_df.iloc[:, correction_column_index]

    has_correction = corrected_ids.notna()
    n_corrected = int(has_correction.sum())

    df.loc[has_correction, subject_id_column,] = corrected_ids.loc[has_correction].values

    return df, n_corrected
     
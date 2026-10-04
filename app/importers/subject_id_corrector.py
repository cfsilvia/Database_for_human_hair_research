import pandas as pd


def correct_subject_ids(
    questionnaire_df: pd.DataFrame,
    correction_df: pd.DataFrame,
    subject_id_column: str = "subject id",
    started_column: str = "started",
    ended_column: str = "ended",
    corrected_id_column_index: int = 11,   # Excel column L
):
    df = questionnaire_df.copy()
    corr = correction_df.copy()

    corrected_col = corr.columns[corrected_id_column_index]
    
    
     # ----------------------------------
    # Make Subject IDs numeric
    # ----------------------------------

    df[subject_id_column] = pd.to_numeric(df[subject_id_column], errors="coerce",).astype("Int64")

    corr[corrected_col] = pd.to_numeric(corr[corrected_col], errors="coerce",).astype("Int64")


    # Keep only rows that actually contain a corrected Subject ID
    corr = corr[corr[corrected_col].notna()].copy()

    # Create a lookup using started + ended
    correction_lookup = corr.set_index(
        [started_column, ended_column]
    )[corrected_col]

    # Build the same key in the questionnaire
    questionnaire_keys = pd.MultiIndex.from_frame(
        df[[started_column, ended_column]]
    )

    # Find rows that appear in the correction file

    mask = questionnaire_keys.isin(
        correction_lookup.index
    )

    # Replace only those Subject IDs
    df.loc[mask, subject_id_column] = [
        correction_lookup.loc[key]
        for key in questionnaire_keys[mask]
    ]

    return df, int(mask.sum())
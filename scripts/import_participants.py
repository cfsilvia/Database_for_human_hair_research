from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


from app.database.connection import SessionLocal
from app.importers.participant_importer import import_participants
from app.importers.subject_id_corrector import correct_subject_ids
from app.importers.excel_reader import read_questionnaire_file



def normalize_columns(df):
    df = df.copy()

    df.columns = [
        str(col).strip().lower()
        for col in df.columns
    ]

    return df


def run():

    questionnaire_df = read_questionnaire_file(
        PROJECT_ROOT
        / "data"
        / "incoming"
        / "שאלון 2 מספרי 20.9.xlsx"
    )

    correction_df = pd.read_excel(
        PROJECT_ROOT
        / "data"
        / "incoming"
        / "Second_Questionnarie_Correction.xlsx"
    )

   
    correction_df = normalize_columns(correction_df)

    questionnaire_df, n_corrected = correct_subject_ids(questionnaire_df=questionnaire_df, correction_df=correction_df,)

    print(
        f"Corrected Subject IDs: {n_corrected}"
    )

    db = SessionLocal()

    try:
        result = import_participants(db=db,df=questionnaire_df,)

        print(result)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    run()
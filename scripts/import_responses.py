from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import SessionLocal
from app.importers.subject_id_corrector import correct_subject_ids
from app.importers.response_importer import import_responses
from app.importers.excel_reader import read_questionnaire_file



def run():

    questionnaire_df = read_questionnaire_file(
        PROJECT_ROOT
         / "data"
        / "incoming"
        / "שאלון 2 מספרי 20.9.xlsx",
        
    )
    
    

    correction_df = pd.read_excel(
        PROJECT_ROOT
        / "data"
        / "incoming"
        / "Second_Questionnarie_Correction.xlsx"
    )
    
    code_questionnarie ="second-questionnaire"
    
    correction_df.columns = (
        correction_df.columns
        .str.strip()
        .str.lower()
    )

    questionnaire_df, n_corrected = correct_subject_ids(
        questionnaire_df=questionnaire_df,
        correction_df=correction_df,
        subject_id_column="subject id",
        started_column="started",
        ended_column="ended",
    )

    print(f"Corrected IDs: {n_corrected}")

    db = SessionLocal()

    try:

        result = import_responses(
            db=db,
            df=questionnaire_df,
            questionnaire_code=code_questionnarie,
        )

        print(result)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    run()
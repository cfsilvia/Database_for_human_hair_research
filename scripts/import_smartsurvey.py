
from pathlib import Path
import sys
import pandas as pd
from sqlalchemy import select, func

# ==========================================
# PATHS
# ==========================================

PROJECT_ROOT = Path(
    r"D:\Database_for_human_hair_research"
)

DATA_DIR = Path(
    r"D:\HairProject\SmartSurvey"
)

CORRECTION_DIR = DATA_DIR / "auxiliary data"

sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import SessionLocal
from app.database.models import (
    Participant,
    Questionnaire,
    QuestionnaireSession,
)
from app.importers.excel_reader import read_questionnaire_file
from app.importers.subject_id_corrector import correct_subject_ids
from app.importers.participant_importer import import_participants
from app.importers.session_importer import import_sessions
from app.importers.response_importer import import_responses


# ==========================================
# SAFETY CONFIGURATION
# ==========================================

# True = ask before saving validated changes
# False = save validated changes automatically
DRY_RUN = True

QUESTIONNAIRES = [
    {
        "code": "first-questionnaire",
        "survey_id": "1781743",
        "prefix": "Questionnaire1_",
        "correction": "First_Questionnarie_Correction.xlsx",
    },
    {
        "code": "second-questionnaire",
        "survey_id": "1781777",
        "prefix": "Questionnaire2_",
        "correction": "Second_Questionnarie_Correction.xlsx",
    },
]


# ==========================================
# FIND LATEST EXPORT
# ==========================================

'''Find the matching Excel export with the newest modification time.

Input: config dictionary containing prefix, survey_id, and code.
Output: Path to the latest matching file in DATA_DIR.
Raises FileNotFoundError if no matching export exists.
'''

def find_latest_file(config):

    pattern = (
        config["prefix"]
        + "RawData-"
        + config["survey_id"]
        + "-*.xlsx"
    )

    files = list(DATA_DIR.glob(pattern))

    if not files:
        raise FileNotFoundError(
            f"No export found for {config['code']}"
        )

    # Use file modification time, not filename order
    latest = max(
        files,
        key=lambda p: p.stat().st_mtime
    )

    return latest


# ==========================================
# LOAD AND CORRECT DATA
# ==========================================

'''Read the latest export, correct subject IDs, and check for duplicates.

Input: questionnaire config containing export details and correction filename.
Output: pandas DataFrame with corrected subject IDs.
Raises FileNotFoundError for missing files or ValueError for invalid data.
'''

def load_questionnaire(config):

    filename = find_latest_file(config)

    print("\nQuestionnaire:", config["code"])
    print("File:", filename.name)

    df = read_questionnaire_file(filename)

    correction_path = (
        CORRECTION_DIR / config["correction"]
    )

    if not correction_path.is_file():
        raise FileNotFoundError(correction_path)

    correction_df = pd.read_excel(correction_path)

    correction_df.columns = [
        str(col).strip().lower()
        for col in correction_df.columns
    ]

    df, corrected = correct_subject_ids(
        questionnaire_df=df,
        correction_df=correction_df,
        subject_id_column="subject id",
        started_column="started",
        ended_column="ended",
    )

    print("Rows:", len(df))
    print("Corrected Subject IDs:", corrected)

    if "subject id" not in df.columns:
        raise ValueError("Missing subject id column")

    # Prevent duplicate subject/questionnaire rows
    valid_ids = df["subject id"].dropna()

    if valid_ids.duplicated().any():
        raise ValueError(
            "Duplicate Subject IDs found in "
            + config["code"]
            + ". Review the export before importing."
        )

    return df


# ==========================================
# DATABASE COUNTS
# ==========================================

'''Print the participant total and session count for each questionnaire.

Input: an open SQLAlchemy database session.
Output: None; counts are printed to the console.
'''

def database_counts(db):

    participants = db.scalar(
        select(func.count()).select_from(Participant)
    )

    print("\nTotal participants:", participants)

    rows = db.execute(
        select(
            Questionnaire.code,
            func.count(QuestionnaireSession.id)
        )
        .outerjoin(
            QuestionnaireSession,
            QuestionnaireSession.questionnaire_id
            == Questionnaire.id
        )
        .group_by(Questionnaire.code)
    ).all()

    for code, count in rows:
        print(code, "sessions:", count)


# ==========================================
# IMPORT ONE QUESTIONNAIRE
# ==========================================

'''Import participants, sessions, and responses for new sessions.

Input: an open database session, questionnaire config, and corrected DataFrame.
Output: dictionary with participants, sessions, and responses import results.
Changes are not committed here; run() controls the transaction.
Raises ValueError for missing mappings or required data, or skipped import rows.
'''

def process_questionnaire(db, config, df):

    print("\nProcessing:", config["code"])

    participant_result = import_participants(
        db=db,
        df=df,
    )

    session_result = import_sessions(
        db=db,
        df=df,
        questionnaire_code=config["code"],
    )

    new_session_ids = set(
        session_result["created_session_ids"]
    )

    response_result = import_responses(
        db=db,
        df=df,
        questionnaire_code=config["code"],
        created_session_ids=new_session_ids,
    )

    print("Participants:", participant_result)
    print(
        "Sessions created:",
        session_result["created"]
    )
    print(
        "Sessions already existing:",
        session_result["existing"]
    )
    print(
        "Responses inserted:",
        response_result["inserted"]
    )

    # Do not silently accept missing data mappings
    if response_result["missing_question"] > 0:
        raise ValueError(
            "Missing question variants: "
            + str(response_result["missing_question"])
        )

    if response_result["missing_session"] > 0:
        raise ValueError(
            "Missing questionnaire sessions: "
            + str(response_result["missing_session"])
        )

    if session_result["missing_wording"] > 0:
        raise ValueError(
            "Missing wording forms: "
            + str(session_result["missing_wording"])
        )

    if session_result["skipped"] > 0:
        raise ValueError(
            "Skipped session rows: "
            + str(session_result["skipped"])
        )

    if participant_result["skipped"] > 0:
        raise ValueError(
            "Skipped participant rows: "
            + str(participant_result["skipped"])
        )

    return {
        "participants": participant_result,
        "sessions": session_result,
        "responses": response_result,
    }


# ==========================================
# MAIN
# ==========================================

'''Load both questionnaires and manage the database import transaction.

Input: auto_save (bool), default False. True saves validated changes without
    prompting. False follows DRY_RUN: ask if True, save automatically if False.
Output: None; progress and the final result are printed to the console.
Import errors roll back the transaction and are raised to the caller.
'''

def run(auto_save=False):

    print("=" * 50)
    print("SMARTSURVEY DATABASE IMPORT")
    print("DRY RUN:", DRY_RUN and not auto_save)
    print("=" * 50)

    # Validate and load both files first
    datasets = []

    for config in QUESTIONNAIRES:
        df = load_questionnaire(config)
        datasets.append((config, df))

    db = SessionLocal()

    try:
        print("\nDATABASE BEFORE IMPORT")
        database_counts(db)

        for config, df in datasets:
            process_questionnaire(
                db,
                config,
                df,
            )

        # Automatic saving overrides DRY_RUN after validation succeeds.
        save_changes = auto_save or not DRY_RUN

        # Otherwise, keep the manual confirmation when DRY_RUN is enabled.
        if DRY_RUN and not auto_save:
            try:
                answer = input("Save these changes to PostgreSQL? [yes/no]: ")
            except (EOFError, OSError):
                answer = "no"
            save_changes = answer.strip().lower() == "yes"

        if not save_changes:
            db.rollback()
            print("\nDRY RUN COMPLETED")
            print("All changes rolled back.")
            print("Database was not updated.")

        else:
            db.commit()
            print("\nIMPORT COMPLETED")
            print("Changes saved to PostgreSQL.")

    except Exception:
        db.rollback()
        print("\nIMPORT FAILED")
        print("Database transaction rolled back.")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    run()

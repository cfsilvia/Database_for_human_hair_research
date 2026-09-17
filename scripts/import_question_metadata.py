from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import SessionLocal
from app.importers.question_metadata import build_question_metadata
from app.importers.canonical_mapper import assign_canonical_questions
from app.importers.metadata_importer import import_metadata


def run_metadata_import():

    df = build_question_metadata(
       data_folder="D:\\Database_for_human_hair_research\\data\\data_of_questionaries",
    output_file="questions.xlsx")

    df = assign_canonical_questions(
        df
    )

    db = SessionLocal()

    try:
        result = import_metadata(
            db=db,
            df=df,
        )

        print(result)

    finally:
        db.close()


if __name__ == "__main__":
    run_metadata_import()
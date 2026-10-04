from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


from app.database.connection import SessionLocal
from app.importers.metadata_importer import import_metadata_workbook

def run():

    metadata_file = (
        PROJECT_ROOT
        / "data"
        / "incoming"
        / "question_metadata.xlsx"
    )

    db = SessionLocal()

    try:

        results = import_metadata_workbook(db=db, excel_path=metadata_file,)

        for test_name, result in results.items():
            print(test_name,result,)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    run()
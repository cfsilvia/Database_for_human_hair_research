
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


from app.database.connection import SessionLocal
from app.importers.questionnaire_scoring import (
    DEFAULT_WORKBOOK,
    import_scoring_workbook,
)

# Excel file
EXCEL_FILE = Path(r"D:\Database_for_human_hair_research\data\incoming\Quest and scoring_to_use.xlsx")

# False = preview only
# True = save to database
APPLY = True


def main():
    with SessionLocal() as db:
        try:
            results = import_scoring_workbook(
                db,
                file_path=EXCEL_FILE,
                apply=APPLY,
            )

            for table_name, result in results.items():
                print(f"\n{table_name}")
                print(f"New: {result['new']}")
                print(f"Existing: {result['existing']}")

            if APPLY:
                db.commit()
                print("\nImport completed.")
            else:
                db.rollback()
                print("\nPreview only. No changes saved.")

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()

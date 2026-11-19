from pathlib import Path
import sys

from openpyxl import load_workbook
from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import SessionLocal
from app.database.models import Locality


EXCEL_FILE = PROJECT_ROOT / "data" / "incoming" / "location_datagov.xlsx"

COLUMNS = (
    "locality_he",
    "district_code",
    "district_he",
    "subdistrict_code",
    "subdistrict_he",
)


def read_localities(file_path):
    workbook = load_workbook(file_path, read_only=True, data_only=True)

    try:
        sheet = workbook.worksheets[0]
        rows = sheet.iter_rows(values_only=True)

        if next(rows, None) != COLUMNS:
            raise ValueError("Unexpected Excel column headers.")

        records = []

        for row_number, values in enumerate(rows, start=2):
            if all(value is None for value in values):
                continue

            if any(value is None for value in values):
                raise ValueError(f"Missing value at Excel row {row_number}.")

            records.append(values)

        return records
    finally:
        workbook.close()


def import_localities(file_path):
    records = read_localities(file_path)
    inserted = 0

    with SessionLocal.begin() as db:
        existing = {
            tuple(row)
            for row in db.execute(
                select(
                    Locality.locality_he,
                    Locality.district_code,
                    Locality.district_he,
                    Locality.subdistrict_code,
                    Locality.subdistrict_he,
                )
            )
        }

        for values in records:
            if values in existing:
                continue

            record = dict(zip(COLUMNS, values))
            locality = Locality(**record)
            db.add(locality)
            existing.add(values)
            inserted += 1

    print(f"Imported {inserted} new localities.")


if __name__ == "__main__":
    import_localities(EXCEL_FILE)

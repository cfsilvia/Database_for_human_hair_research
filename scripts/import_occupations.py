from pathlib import Path
import sys

from openpyxl import load_workbook
from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import SessionLocal
from app.database.models import Occupation


def read_occupations(file_path):
    workbook = load_workbook(file_path, read_only=True, data_only=True)

    try:
        sheet = workbook["All occupations"]
        rows = sheet.iter_rows(values_only=True)

        expected_headers = (
            "Major code",
            "Major group (Hebrew)",
            "First group code",
            "First group (Hebrew)",
            "Second group code",
            "Second group (Hebrew)",
            "Occupation code",
            "Occupation (Hebrew)",
            "PDF printed page",
        )
        if next(rows, None) != expected_headers:
            raise ValueError("Unexpected occupation column headers.")

        fields = (
            "major_code",
            "major_group_he",
            "first_group_code",
            "first_group_he",
            "second_group_code",
            "second_group_he",
            "occupation_code",
            "occupation_he",
        )
        records = []

        for row_number, row in enumerate(rows, start=2):
            if all(value is None for value in row):
                continue

            values = row[:8]

            if any(value is None or not str(value).strip() for value in values):
                raise ValueError(f"Missing required value at Excel row {row_number}.")

            records.append(dict(zip(fields, (str(value).strip() for value in values))))

        return records
    finally:
        workbook.close()


def import_occupations(file_path):
    records = read_occupations(file_path)
    inserted = 0

    with SessionLocal.begin() as db:
        existing_codes = set(db.scalars(select(Occupation.occupation_code)))

        for record in records:
            code = record["occupation_code"]

            if code in existing_codes:
                continue

            db.add(Occupation(**record))
            existing_codes.add(code)
            inserted += 1

    print(f"Imported {inserted} new occupations.")


def main():
    file_path = (
        PROJECT_ROOT
        / "data"
        / "incoming"
        / "CBS_2011_occupations_COMPLETE.xlsx"
    )

    import_occupations(file_path)


if __name__ == "__main__":
    main()

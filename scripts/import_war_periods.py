from pathlib import Path
import sys

from openpyxl import load_workbook
from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import SessionLocal
from app.database.models import WarPeriod


EXCEL_FILE = PROJECT_ROOT / "data" / "incoming" / "location.xlsx"


def read_war_periods(file_path):
    workbook = load_workbook(file_path, read_only=True, data_only=True)

    try:
        sheet = workbook["war"]
        periods = []

        for name, start_date, end_date in sheet.iter_rows(
            min_row=2, max_col=3, values_only=True
        ):
            if name is None:
                continue

            periods.append((
                name,
                start_date.date(),
                end_date.date(),
            ))

        return periods
    finally:
        workbook.close()


def main():
    periods = read_war_periods(EXCEL_FILE)

    with SessionLocal.begin() as db:
        for name, start_date, end_date in periods:
            period = db.scalar(
                select(WarPeriod).where(WarPeriod.name == name)
            )

            if period is None:
                period = WarPeriod(name=name)
                db.add(period)

            period.start_date = start_date
            period.end_date = end_date

    print(f"Imported {len(periods)} war periods.")


if __name__ == "__main__":
    main()

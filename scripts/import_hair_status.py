import argparse
from collections import Counter
from pathlib import Path
import sys

from openpyxl import load_workbook
from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.models import Participant


EXCEL_FILE = Path("D:/HairProject/SmartSurvey/Follow_participants_hair_project.xlsm")
SHEET_NAME = "קישורים לשאלונים"
ID_HEADER = "מס נבדק"
STATUS_HEADER = "gave hair Yes/No/Wait"


def read_hair_status(file_path):
    workbook = load_workbook(file_path, read_only=True, data_only=True)
    try:
        sheet = workbook[SHEET_NAME]
        rows = sheet.iter_rows(values_only=True)
        headers = [" ".join(str(value or "").split()) for value in next(rows, ())]
        for header in (ID_HEADER, STATUS_HEADER):
            if headers.count(header) != 1:
                raise ValueError(f"Expected exactly one column named '{header}'.")
        id_column = headers.index(ID_HEADER)
        status_column = headers.index(STATUS_HEADER)
        records = []
        seen = set()
        for row_number, row in enumerate(
            rows, start=2
        ):
            participant_id, status = row[id_column], row[status_column]
            if participant_id is None and status is None:
                continue
            value = str(participant_id).strip()
            if not value.isascii() or not value.isdigit():
                raise ValueError(f"Invalid participant ID at Excel row {row_number}.")
            subject_id = int(value)
            if subject_id in seen:
                raise ValueError(f"Duplicate participant ID at Excel row {row_number}.")
            seen.add(subject_id)
            if status is None or not str(status).strip():
                continue
            records.append((row_number, subject_id, str(status)))
        return records
    finally:
        workbook.close()


def update_hair_status(db, records):
    participants = {
        participant.subject_id: participant
        for participant in db.scalars(select(Participant))
    }
    counts = {"updated": 0, "unchanged": 0, "unmatched": 0}
    for row_number, subject_id, status in records:
        participant = participants.get(subject_id)
        if participant is None:
            print(f"Unmatched: Excel row {row_number}, subject_id {subject_id}")
            counts["unmatched"] += 1
        elif participant.gave_hair == status:
            counts["unchanged"] += 1
        else:
            participant.gave_hair = status
            counts["updated"] += 1
    return counts


def run(file_path=EXCEL_FILE, apply=False):
    records = read_hair_status(file_path)
    print(f"Nonblank source records: {len(records)}")
    print(f"{STATUS_HEADER} values:", dict(Counter(status for _, _, status in records)))
    if not apply:
        print("Preview only. Blank cells are skipped. Use --apply to update existing participants.")
        return

    from app.database.connection import SessionLocal

    with SessionLocal.begin() as db:
        counts = update_hair_status(db, records)
    print(counts)


def main():
    parser = argparse.ArgumentParser(description="Import hair status using named Excel columns.")
    parser.add_argument("file", nargs="?", type=Path, default=EXCEL_FILE)
    parser.add_argument("--apply", action="store_true", help="Write values to the database.")
    args = parser.parse_args()
    run(file_path=args.file, apply=args.apply)


if __name__ == "__main__":
    main()

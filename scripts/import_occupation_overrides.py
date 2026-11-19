"""Import saved AI findings; this does not change questionnaire answers."""

import argparse
from pathlib import Path
import sys

from openpyxl import load_workbook
from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.models import OccupationOverride, Participant


def read_occupation_overrides(file_path):
    workbook = load_workbook(file_path, read_only=True, data_only=True)
    try:
        sheet = workbook["Participants"]
        if sheet.cell(4, 1).value != "participant/subject_id":
            raise ValueError("Unexpected participant ID header.")
        expected = (
            "First table: Major code", "First table: Major group (Hebrew)",
            "First table: First group code", "First table: First group (Hebrew)",
            "First table: Second group code", "First table: Second group (Hebrew)",
        )
        headers = next(sheet.iter_rows(min_row=5, max_row=5, values_only=True))
        if (len(headers) < 14 or headers[5:11] != expected
                or headers[13] != "First table: Classification review"):
            raise ValueError("Unexpected AI classification headers.")
        fields = (
            "major_code", "major_group_he", "first_group_code",
            "first_group_he", "second_group_code", "second_group_he",
        )
        records = []
        seen = set()
        for row_number, row in enumerate(sheet.iter_rows(min_row=6, values_only=True), 6):
            if all(value is None for value in row):
                continue
            subject_id = row[0]
            if isinstance(subject_id, bool) or not isinstance(subject_id, int):
                raise ValueError(f"Invalid participant ID at row {row_number}.")
            if subject_id in seen:
                raise ValueError(f"Duplicate participant ID: {subject_id}.")
            seen.add(subject_id)
            if not str(row[1] or "").strip() or any(
                value is None or not str(value).strip() for value in row[5:11]
            ):
                raise ValueError(f"Missing occupation answer or AI value at row {row_number}.")
            records.append({
                "subject_id": subject_id,
                "occupation_answer": str(row[1]),
                **dict(zip(fields, (str(value).strip() for value in row[5:11]))),
                "review": str(row[13]) if row[13] is not None else "",
                "source_filename": Path(file_path).name,
            })
        if not records:
            raise ValueError("No AI occupation records found.")
        return records
    finally:
        workbook.close()


def save_occupation_overrides(db, records):
    """Validate before writing; the caller owns the transaction."""
    participant_ids = set(db.scalars(select(Participant.subject_id)))
    missing = {record["subject_id"] for record in records} - participant_ids
    if missing:
        raise ValueError(f"Participants do not exist: {sorted(missing)}")
    existing = {item.subject_id: item for item in db.scalars(select(OccupationOverride))}
    inserted = 0
    for record in records:
        item = existing.get(record["subject_id"])
        if item is None:
            db.add(OccupationOverride(**record))
            inserted += 1
        else:
            for field, value in record.items():
                setattr(item, field, value)
    return inserted, len(records) - inserted


def import_occupation_overrides(file_path):
    from app.database.connection import SessionLocal

    records = read_occupation_overrides(file_path)
    with SessionLocal.begin() as db:
        inserted, updated = save_occupation_overrides(db, records)
    print(f"Imported {inserted} AI occupation overrides; updated {updated}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file_path", type=Path)
    import_occupation_overrides(parser.parse_args().file_path)

from openpyxl import Workbook
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database.models import OccupationOverride, Participant
from scripts.import_occupation_overrides import read_occupation_overrides, save_occupation_overrides


def make_workbook(tmp_path, ids=(101,)):
    path = tmp_path / "comparison.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Participants"
    sheet.cell(4, 1, "participant/subject_id")
    headers = [
        "First table: Major code", "First table: Major group (Hebrew)",
        "First table: First group code", "First table: First group (Hebrew)",
        "First table: Second group code", "First table: Second group (Hebrew)",
    ]
    for column, header in enumerate(headers, 6):
        sheet.cell(5, column, header)
    sheet.cell(5, 14, "First table: Classification review")
    for row, subject_id in enumerate(ids, 6):
        for column, value in enumerate([
            subject_id, "עיסוק", None, None, None,
            "0\n2", "צבא\nאקדמי", "01\n25", "קבוצה\nקבוצה",
            "011\n251", "תפקיד\nתפקיד", None, None, "בדיקה נדרשת",
        ], 1):
            sheet.cell(row, column, value)
    workbook.save(path)
    workbook.close()
    return path


@pytest.mark.parametrize("ids", [(101, 101), (None,), (True,), ("bad",)])
def test_rejects_bad_ids(tmp_path, ids):
    with pytest.raises(ValueError):
        read_occupation_overrides(make_workbook(tmp_path, ids))


def test_rejects_wrong_headers_and_missing_classification(tmp_path):
    from openpyxl import load_workbook

    for cell, value in (("F5", "Wrong source"), ("F6", None), ("B6", None)):
        path = make_workbook(tmp_path)
        workbook = load_workbook(path)
        workbook["Participants"][cell].value = value
        workbook.save(path)
        workbook.close()
        with pytest.raises(ValueError):
            read_occupation_overrides(path)


def test_import_preserves_roles_and_is_repeatable(tmp_path):
    records = read_occupation_overrides(make_workbook(tmp_path))
    assert records[0]["major_code"] == "0\n2"
    assert records[0]["review"] == "בדיקה נדרשת"
    engine = create_engine("sqlite://")
    Participant.__table__.create(engine)
    OccupationOverride.__table__.create(engine)
    with Session(engine) as db:
        db.add(Participant(subject_id=101))
        db.commit()
        assert save_occupation_overrides(db, records) == (1, 0)
        db.commit()
        assert save_occupation_overrides(db, records) == (0, 1)
        db.commit()
        assert len(list(db.scalars(select(OccupationOverride)))) == 1
        assert db.get(OccupationOverride, 101).major_code == "0\n2"
    engine.dispose()


def test_missing_participant_causes_no_partial_writes(tmp_path):
    records = read_occupation_overrides(make_workbook(tmp_path, (101, 102)))
    engine = create_engine("sqlite://")
    Participant.__table__.create(engine)
    OccupationOverride.__table__.create(engine)
    with Session(engine) as db:
        db.add(Participant(subject_id=101))
        db.commit()
        with pytest.raises(ValueError, match="102"):
            save_occupation_overrides(db, records)
        assert not db.new
    engine.dispose()

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database.models import Participant
from scripts.import_hair_status import (
    ID_HEADER, STATUS_HEADER, SHEET_NAME, read_hair_status, update_hair_status,
)


class HairStatusImportTests(unittest.TestCase):
    def write_workbook(self, directory, values):
        path = Path(directory) / "tracking.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = SHEET_NAME
        sheet.append([None] * 7 + [ID_HEADER] + [None] * 6 + [STATUS_HEADER])
        for subject_id, status in values:
            sheet.append([None] * 7 + [subject_id] + [None] * 6 + [status])
        workbook.save(path)
        workbook.close()
        return path

    def test_reads_column_o_without_conversion_and_skips_blanks(self):
        with TemporaryDirectory() as directory:
            path = self.write_workbook(directory, [
                ("0001", "Yes"), (2, "No"), (3, "Wait"),
                (4, "המתנה"), (5, None), (6, "F"),
            ])
            self.assertEqual(read_hair_status(path), [
                (2, 1, "Yes"), (3, 2, "No"), (4, 3, "Wait"),
                (5, 4, "המתנה"), (7, 6, "F"),
            ])

    def test_rejects_invalid_and_duplicate_ids(self):
        with TemporaryDirectory() as directory:
            for values in [[("invalid", "Yes")], [(None, "Yes")],
                           [("0001", "Yes"), (1, "No")]]:
                with self.subTest(values=values):
                    path = self.write_workbook(directory, values)
                    with self.assertRaises(ValueError):
                        read_hair_status(path)

    def test_finds_columns_by_header_after_reordering(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "reordered.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = SHEET_NAME
            sheet.append(["gave   hair Yes/No/Wait", ID_HEADER])
            sheet.append(["Wait", "0001"])
            workbook.save(path)
            workbook.close()
            self.assertEqual(read_hair_status(path), [(2, 1, "Wait")])

    def test_rejects_old_workbook_without_status_header(self):
        with TemporaryDirectory() as directory:
            path = self.write_workbook(directory, [("0001", "F")])
            from openpyxl import load_workbook
            workbook = load_workbook(path)
            workbook[SHEET_NAME].cell(1, 15, "נשים")
            workbook.save(path)
            workbook.close()
            with self.assertRaisesRegex(ValueError, STATUS_HEADER):
                read_hair_status(path)

    def test_updates_by_subject_id_without_creating_participants(self):
        engine = create_engine("sqlite://")
        Participant.__table__.create(engine)
        try:
            with Session(engine) as db:
                db.add_all([Participant(id=10, subject_id=1),
                            Participant(id=11, subject_id=2, gave_hair="Wait")])
                db.commit()
                records = [(2, 1, "Yes"), (3, 3, "No")]
                self.assertEqual(update_hair_status(db, records),
                                 {"updated": 1, "unchanged": 0, "unmatched": 1})
                db.commit()
                self.assertEqual(update_hair_status(db, records),
                                 {"updated": 0, "unchanged": 1, "unmatched": 1})
                participants = db.scalars(select(Participant).order_by(Participant.id)).all()
                self.assertEqual([(p.subject_id, p.gave_hair) for p in participants],
                                 [(1, "Yes"), (2, "Wait")])
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()

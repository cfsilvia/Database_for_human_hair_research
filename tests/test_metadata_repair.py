import pandas as pd
import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.database.models import (
    Base, CanonicalQuestion, Participant, Questionnaire, QuestionnaireSession,
    QuestionVariant, Response, ResponseValueLabel,
)
from app.importers.canonical_mapper import assign_canonical_questions
from app.importers.metadata_importer import import_metadata_dataframe, import_metadata_workbook
from scripts.repair_pcl_metadata import read_items, repair_metadata, response_digest


@pytest.fixture
def metadata_db(tmp_path):
    rows = []
    for gender, offset in (("male", 0), ("female", 100)):
        for number in range(1, 5):
            rows.append({
                "number question": f"Q{number + offset}",
                "question": f"Question wording {number}",
                "questionnaire": "first-questionnaire", "file name": "PCL",
                "gender_form": gender,
            })
    old = tmp_path / "old.xlsx"
    current = tmp_path / "current.xlsx"
    pd.DataFrame(rows).to_excel(old, sheet_name="PCL", index=False)
    with pd.ExcelWriter(current) as writer:
        for test, numbers in (("PCL", (3, 4)), ("trauma-checklist", (1, 2))):
            selected = [dict(row, **{"file name": test}) for row in rows
                        if int(row["number question"][1:]) % 100 in numbers]
            pd.DataFrame(selected).to_excel(writer, sheet_name=test, index=False)
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine, autoflush=False) as db:
        import_metadata_workbook(db, old)
        participant = Participant(subject_id=123)
        db.add(participant)
        db.flush()
        form = db.scalar(select(Questionnaire))
        session = QuestionnaireSession(participant_id=participant.id, questionnaire_id=form.id)
        db.add(session)
        db.flush()
        variants = db.scalars(select(QuestionVariant).order_by(QuestionVariant.id)).all()
        for variant in variants:
            db.add(Response(session_id=session.id, question_variant_id=variant.id, value_numeric=2))
        symptom = next(v for v in variants if v.question_number == "Q3")
        db.add(ResponseValueLabel(question_id=symptom.canonical_question_id, option_position=1,
                                  numeric_value=2, text_male="label", text_female="label",
                                  source_sheet="PCL", source_row=2))
        db.commit()
        yield db, old, current
    engine.dispose()


def simulate_old_import(db, current):
    for test in ("PCL", "trauma-checklist"):
        df = assign_canonical_questions(pd.read_excel(current, sheet_name=test))
        import_metadata_dataframe(db, df)


@pytest.mark.parametrize("already_imported", [False, True])
def test_repair_preserves_original_records_answers_and_labels(metadata_db, already_imported):
    db, old, current = metadata_db
    original = {v.id: v.canonical_question_id for v in db.scalars(select(QuestionVariant))}
    before = response_digest(db, original)
    label_question = db.scalar(select(ResponseValueLabel.question_id))
    if already_imported:
        simulate_old_import(db, current)
    result = repair_metadata(db, current, old)
    assert result["duplicates_removed"] == (4 if already_imported else 0)
    assert {v.id: v.canonical_question_id for v in db.scalars(select(QuestionVariant))} == original
    assert response_digest(db, original) == before
    assert db.scalar(select(ResponseValueLabel.question_id)) == label_question
    desired = read_items(current, ("PCL", "trauma-checklist"))
    for variant in db.scalars(select(QuestionVariant)):
        row = desired[("first-questionnaire", variant.gender_form, variant.question_number)]
        canonical = db.get(CanonicalQuestion, variant.canonical_question_id)
        assert (variant.file_name, canonical.test_psicolog, canonical.item_order) == (
            row["file name"], row["file name"], int(row["item_order"]))
    assert len(db.scalars(select(CanonicalQuestion)).all()) == 4
    db.commit()
    assert repair_metadata(db, current, old)["changed"] is False
    assert all(r["variants_existing"] == 4 for r in import_metadata_workbook(db, current).values())


def test_import_refuses_renumbering_before_any_changes(metadata_db):
    db, old, current = metadata_db
    before = {v.id: v.canonical_question_id for v in db.scalars(select(QuestionVariant))}
    with pytest.raises(ValueError, match="numbering changed"):
        import_metadata_workbook(db, current)
    assert {v.id: v.canonical_question_id for v in db.scalars(select(QuestionVariant))} == before
    assert len(db.scalars(select(CanonicalQuestion)).all()) == 4


def test_repair_refuses_to_delete_answered_duplicates(metadata_db):
    db, old, current = metadata_db
    simulate_old_import(db, current)
    duplicate = db.scalar(select(QuestionVariant).where(QuestionVariant.file_name == "trauma-checklist"))
    db.add(Response(session_id=db.scalar(select(QuestionnaireSession.id)),
                    question_variant_id=duplicate.id, value_numeric=1))
    db.flush()
    before = {v.id: v.canonical_question_id for v in db.scalars(select(QuestionVariant))}
    with pytest.raises(ValueError, match="have answers"):
        repair_metadata(db, current, old)
    assert {v.id: v.canonical_question_id for v in db.scalars(select(QuestionVariant))} == before


def test_repair_can_be_rolled_back(metadata_db):
    db, old, current = metadata_db
    simulate_old_import(db, current)
    before = [(v.id, v.canonical_question_id, v.file_name)
              for v in db.scalars(select(QuestionVariant).order_by(QuestionVariant.id))]
    repair_metadata(db, current, old)
    db.rollback()
    after = [(v.id, v.canonical_question_id, v.file_name)
             for v in db.scalars(select(QuestionVariant).order_by(QuestionVariant.id))]
    assert before == after

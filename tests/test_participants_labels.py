"""Exercise label resolution with an isolated, in-memory database."""

import os
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.models import (
    Base, CanonicalQuestion, Participant, Questionnaire, QuestionnaireSession,
    QuestionVariant, Response, ResponseValueLabel,
)


def test_table_labels_follow_selected_response_and_keep_original_values():
    # Importing the app needs configuration, but this test never connects to PostgreSQL.
    with patch.dict(os.environ, {"DATABASE_URL": "sqlite://"}):
        from app.main import get_participants_table

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Questionnaire(id=1, code="first-questionnaire", name="Test"))
        db.add(Participant(id=1, subject_id=101))
        db.add(QuestionnaireSession(id=1, participant_id=1, questionnaire_id=1))
        for question_id in range(1, 8):
            db.add(CanonicalQuestion(
                id=question_id, questionnaire_id=1, code=f"q{question_id}",
                test_psicolog="PSS", item_order=question_id,
            ))
            db.add(QuestionVariant(
                id=question_id, canonical_question_id=question_id,
                questionnaire_id=1, question_number=str(question_id),
                gender_form="female" if question_id == 2 else "male",
            ))
        # Same score, different questions and gender wording; whitespace is no label.
        for question_id in (1, 2, 4, 5):
            db.add(ResponseValueLabel(
                question_id=question_id, option_position=1, numeric_value=0,
                text_male="לעולם לא" if question_id != 5 else " ",
                text_female="אף פעם", source_sheet="PSS", source_row=question_id,
            ))
        values = [(0, None), (0, None), (8, None), (None, "free text"),
                  (0, None), (None, None), (None, None)]
        for question_id, (numeric, text) in enumerate(values, 1):
            db.add(Response(
                id=question_id, session_id=1, question_variant_id=question_id,
                value_numeric=numeric, value_text=text,
            ))
        # Later responses must not supply labels for already-selected text cells.
        db.add(QuestionnaireSession(id=2, participant_id=1, questionnaire_id=1))
        db.add(Response(
            id=8, session_id=2, question_variant_id=4, value_numeric=0,
        ))
        # An empty earlier response must not prevent a later numeric answer.
        db.add(Response(
            id=9, session_id=2, question_variant_id=6, value_numeric=3,
        ))
        db.commit()

        table = get_participants_table(db)
        row = table["rows"][0]
        assert row["canonical_1"] == row["canonical_2"] == 0
        assert row["canonical_3"] == 8
        assert row["canonical_4"] == "free text"
        assert row["canonical_5"] == 0
        assert row["canonical_6"] == 3
        assert row["canonical_7"] == ""
        assert table["answer_labels"] == {
            "101": {"canonical_1": "לעולם לא", "canonical_2": "אף פעם"},
        }
    engine.dispose()

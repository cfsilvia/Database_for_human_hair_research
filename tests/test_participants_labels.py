"""Exercise label resolution with an isolated, in-memory database."""

import os
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.models import (
    Base, CanonicalQuestion, Participant, Questionnaire, QuestionnaireSession,
    QuestionVariant, Response, ResponseValueLabel,
    ParticipantTestScores, QuestionnaireScoringRule,
    WarPeriod,
)


@pytest.mark.parametrize("session_dates,expected", [
    ([], "Not answered"),
    ([("2026-03-01", "2026-03-02")], "Iran I"),
    ([("2026-02-27", "2026-02-28")], "Iran I"),
    ([("2026-04-08", "2026-04-09")], "Iran I"),
    ([("2026-06-07", "2026-06-08")], "Iran II"),
    ([("2026-02-27", "2026-06-09")], "Iran I, Iran II"),
    ([("2026-05-01", "2026-05-02")], "No war"),
    ([(None, None)], "Unknown"),
    ([("2026-03-01", None)], "Iran I"),
    ([(None, "2026-06-08")], "Iran II"),
    ([("2026-05-01", None)], "Unknown"),
    ([("2026-03-02", "2026-03-01")], "Unknown"),
    ([("2026-02-01", "2026-02-02"),
      ("2026-05-01", "2026-05-02")], "No war"),
    ([("2026-03-01", "2026-03-02"),
      ("2026-06-07", "2026-06-08")], "Iran I, Iran II"),
    ([(None, None), ("2026-03-01", "2026-03-02")], "Iran I"),
    ([(None, None), ("2026-05-01", "2026-05-02")], "Unknown"),
])
def test_table_war_columns_use_individual_sessions(session_dates, expected):
    with patch.dict(os.environ, {"DATABASE_URL": "sqlite://"}):
        from app.main import get_participants_table

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Participant(id=1, subject_id=101))
        db.add_all([
            Questionnaire(id=1, code="first-questionnaire", name="First"),
            Questionnaire(id=2, code="second-questionnaire", name="Second"),
            WarPeriod(name="Iran I", start_date=date(2026, 2, 28),
                      end_date=date(2026, 4, 8)),
            WarPeriod(name="Iran II", start_date=date(2026, 6, 7),
                      end_date=date(2026, 6, 8)),
            QuestionnaireSession(participant_id=1, questionnaire_id=2,
                                 started_at=datetime(2026, 6, 7),
                                 ended_at=datetime(2026, 6, 8)),
        ])
        for start, end in session_dates:
            db.add(QuestionnaireSession(
                participant_id=1, questionnaire_id=1,
                started_at=datetime.fromisoformat(start) if start else None,
                ended_at=datetime.fromisoformat(end) if end else None,
            ))
        db.commit()

        table = get_participants_table(db)
        keys = [column["key"] for column in table["fixed_columns"]]
        for number in (1, 2):
            assert keys[keys.index(f"questionnaire_{number}_ended_at") + 1] == (
                f"questionnaire_{number}_war"
            )
        assert table["rows"][0]["questionnaire_1_war"] == expected
        assert table["rows"][0]["questionnaire_2_war"] == "Iran II"
        assert not db.new and not db.dirty
    engine.dispose()


@pytest.mark.parametrize("wordings,expected", [
    (["female", "female"], "female"),
    (["male", "male"], "male"),
    (["female", None], "female"),
    ([None, None], None),
    (["female", "male"], "mixed"),
])
def test_table_wording_uses_answered_sessions(wordings, expected):
    with patch.dict(os.environ, {"DATABASE_URL": "sqlite://"}):
        from app.main import get_participants_table

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Participant(id=1, subject_id=101))
        for index, wording in enumerate(wordings, 1):
            db.add(Questionnaire(id=index, code=("first-questionnaire" if index == 1
                                               else "second-questionnaire"), name="Test"))
            db.add(QuestionnaireSession(
                participant_id=1, questionnaire_id=index, wording_form=wording,
                ended_at=datetime(2026, 1, 1),
            ))
        # An unanswered session must not change the participant's wording group.
        db.add(QuestionnaireSession(
            participant_id=1, questionnaire_id=1, wording_form="other",
        ))
        db.commit()
        row = get_participants_table(db)["rows"][0]
        assert row["wording_form"] == expected
        assert row["answered_both_questionnaires"] == "Yes"
    engine.dispose()


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
        assert table["groups"][0]["columns"][0]["canonical_code"] == "q1"
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


@pytest.mark.parametrize("method,test_name,values,expected", [
    ("average", "IPIP", [1, 4], 7.25),
    ("average", "IPIP", [3, 3, 4], 3.33),
    ("sum", "PHQ", [1, 3], 0),
    ("sum", "PCL", [1, 3], 33),
])
@pytest.mark.parametrize("incomplete", [None, "missing", "text", "one_form"])
@pytest.mark.parametrize("stored_state", ["value", "missing", "null"])
def test_table_reads_stored_scores(method, test_name, values, expected, incomplete, stored_state):
    with patch.dict(os.environ, {"DATABASE_URL": "sqlite://"}):
        from app.main import get_participants_table

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            Questionnaire(id=1, code="first-questionnaire", name="First"),
            Questionnaire(id=2, code="second-questionnaire", name="Second"),
            Participant(id=1, subject_id=101),
            QuestionnaireSession(id=1, participant_id=1, questionnaire_id=1),
            QuestionnaireSession(id=2, participant_id=1, questionnaire_id=2,
                                 ended_at=None if incomplete == "one_form" else
                                 datetime(2026, 1, 1)),
        ])
        for question_id, value in enumerate(values, 1):
            db.add(CanonicalQuestion(
                id=question_id, questionnaire_id=1, code=f"q{question_id}",
                test_psicolog=test_name, item_order=question_id,
            ))
            db.add(QuestionVariant(
                id=question_id, canonical_question_id=question_id,
                questionnaire_id=1, question_number=str(question_id), gender_form="male",
            ))
            if question_id == 2 and incomplete == "missing":
                continue
            db.add(Response(
                session_id=1, question_variant_id=question_id,
                value_numeric=None if question_id == 2 and incomplete == "text" else value,
                value_text="text" if question_id == 2 and incomplete == "text" else None,
            ))
        for rule_id, kind in ((1, "total"), (2, "subscale")):
            db.add(QuestionnaireScoringRule(
                id=rule_id, test_name=test_name, rule_code=kind, rule_type=kind,
                scoring_method=method, subscale_name="PA" if kind == "subscale" else None,
                description_he="רגש חיובי" if kind == "subscale" else None,
                min_score=0, max_score=10,
                source_sheet=f"{test_name}_scoring_rules",
            ))
            if stored_state != "missing":
                db.add(ParticipantTestScores(
                    subject_id=101, rule_id=rule_id,
                    score=None if stored_state == "null" else
                    Decimal(str(expected + rule_id - 1)),
                ))
        db.add(QuestionnaireScoringRule(
            id=3, test_name=test_name, rule_code="interpretation", rule_type="interpretation",
            parent_rule_id=1, range_min=expected, range_max=expected,
            interpretation_he="Matched", source_sheet=f"{test_name}_scoring_rules",
        ))
        db.add(QuestionnaireScoringRule(
            id=4, test_name=test_name, rule_code="disabled", rule_type="interpretation",
            parent_rule_id=1, range_min=0, range_max=10,
            interpretation_he="Disabled", is_enabled=False,
            source_sheet=f"{test_name}_scoring_rules",
        ))
        db.commit()

        table = get_participants_table(db)
        columns = {column["key"]: column for group in table["groups"]
                   for column in group["columns"]}
        assert columns["score_1"]["description"] is None
        assert columns["score_1"]["scoring_method"] == method
        assert columns["score_1"]["min_score"] == 0
        assert columns["score_1"]["max_score"] == 10
        assert columns["score_1"]["interpretation_ranges"] == [
            {"min": expected, "max": expected, "label": "Matched"},
        ]
        assert columns["score_2"]["description"] == "רגש חיובי"
        assert columns["score_2"]["interpretation_ranges"] == []
        assert columns["score_1"]["missing_score_label"] == (
            "No PCL answer" if test_name == "PCL" else "Missing score"
        )
        assert columns["score_2"]["missing_score_label"] == "Missing score"
        row = table["rows"][0]
        has_score = stored_state == "value" and incomplete != "one_form"
        assert row["score_1"] == (round(expected, 2) if has_score else "")
        assert row["score_2"] == (round(expected + 1, 2) if has_score else "")
        if has_score:
            assert isinstance(row["score_1"], float)
        assert row["canonical_1"] == values[0]
        assert row["canonical_2"] == (
            "" if incomplete == "missing" else "text" if incomplete == "text" else values[1]
        )
        assert table["score_interpretations"] == (
            {"101": {"score_1": "Matched"}} if has_score else {}
        )
        assert not db.new and not db.dirty
    engine.dispose()

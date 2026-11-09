from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.database.models import (
    Base, CanonicalQuestion, Participant, ParticipantTestScores, Questionnaire,
    QuestionnaireScoringRule, QuestionnaireSession, QuestionVariant, Response,
    ScoringRuleQuestion,
)
from scripts.populate_participant_test_scores import populate_scores


def test_preview_population_and_repeat():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            Questionnaire(id=1, code="first-questionnaire", name="First"),
            Questionnaire(id=2, code="second-questionnaire", name="Second"),
            Participant(id=1, subject_id=1001), Participant(id=2, subject_id=1002),
        ])
        db.flush()
        for number in (1, 2, 3):
            db.add(CanonicalQuestion(
                id=number, questionnaire_id=1, code=f"q{number}",
                test_psicolog="TEST", item_order=number,
            ))
        db.flush()
        for number in (1, 2, 3):
            db.add(QuestionVariant(
                id=number, canonical_question_id=number, questionnaire_id=1,
                question_number=str(number), gender_form="male",
            ))
        db.add_all([
            QuestionnaireSession(id=1, participant_id=1, questionnaire_id=1),
            QuestionnaireSession(id=2, participant_id=1, questionnaire_id=2,
                                 ended_at=datetime.now(timezone.utc)),
            QuestionnaireSession(id=3, participant_id=2, questionnaire_id=1),
        ])
        rules = [
            (1, "total", "sum", True), (2, "subscale", "average", True),
            (3, "subscale", "sum", True), (4, "total", "sum", False),
            (5, "interpretation", None, True), (6, "total", "sum", True),
        ]
        for rule_id, kind, method, enabled in rules:
            db.add(QuestionnaireScoringRule(
                id=rule_id, test_name="TEST", rule_code=str(rule_id),
                rule_type=kind, scoring_method=method, is_enabled=enabled,
                source_sheet="test",
            ))
        db.flush()
        for rule_id, question_ids in ((1, [1, 2]), (2, [1, 2]), (3, [1, 3])):
            for question_id in question_ids:
                db.add(ScoringRuleQuestion(
                    rule_id=rule_id, question_id=question_id,
                    source_question_number=question_id,
                ))
        db.add_all([
            Response(id=1, session_id=1, question_variant_id=1, value_numeric=1),
            Response(id=2, session_id=1, question_variant_id=2, value_numeric=2.333333),
            Response(id=3, session_id=3, question_variant_id=1, value_numeric=5),
            Response(id=4, session_id=3, question_variant_id=2, value_numeric=5),
        ])
        db.commit()

        preview = populate_scores(db)
        assert preview == {"eligible_participants": 1, "new": 4, "updated": 0,
                           "unchanged": 0, "null_scores": 2}
        assert db.scalars(select(ParticipantTestScores)).all() == []
        assert not db.new and not db.dirty

        assert populate_scores(db, apply=True) == preview
        db.commit()
        stored = {row.rule_id: row for row in db.scalars(select(ParticipantTestScores))}
        assert set(stored) == {1, 2, 3, 6}
        assert all(row.subject_id == 1001 for row in stored.values())
        assert stored[1].score == Decimal("3.33")
        assert stored[2].score == Decimal("1.67")
        assert stored[3].score is None
        assert stored[6].score is None

        repeated = populate_scores(db, apply=True)
        assert repeated["new"] == repeated["updated"] == 0
        assert repeated["unchanged"] == 4
        db.commit()

        created_at = stored[1].created_at
        db.get(Response, 1).value_numeric = 0
        db.commit()
        assert populate_scores(db)["updated"] == 2
        assert stored[1].score == Decimal("3.33")
        populate_scores(db, apply=True)
        db.commit()
        assert stored[1].score == Decimal("2.33")
        assert stored[1].created_at == created_at

        # Earlier numeric answers win over later answers from another session.
        db.add(QuestionnaireSession(id=4, participant_id=1, questionnaire_id=1))
        db.flush()
        db.add(Response(id=5, session_id=4, question_variant_id=1, value_numeric=9))
        db.commit()
        assert populate_scores(db)["unchanged"] == 4

        # A nonempty text answer is not treated as a numeric score.
        db.get(Response, 1).value_numeric = None
        db.get(Response, 1).value_text = "unanswered"
        db.commit()
        populate_scores(db, apply=True)
        db.commit()
        assert stored[1].score is None
        assert stored[2].score is None

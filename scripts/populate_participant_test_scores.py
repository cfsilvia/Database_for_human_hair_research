"""Calculate stored scores from existing responses; preview unless APPLY is True."""

from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.database.models import (
    Participant, ParticipantTestScores, Questionnaire, QuestionnaireScoringRule,
    QuestionnaireSession, QuestionVariant, Response, ScoringRuleQuestion,
)


APPLY = True #if true apply it


# Input: db - an open SQLAlchemy database session.
# Output: a set of participant IDs (participants.id) who answered both questionnaires.
def answered_both_participants(db):
    """Find participants who answered the first and second questionnaires."""
    questionnaire_ids = db.scalars(select(Questionnaire.id).where(
        Questionnaire.code.in_([
                "first-questionnaire",
                "second-questionnaire",
            ])
        )
    ).all()
    
    if len(questionnaire_ids) != 2:
        raise ValueError("Both questionnaires must exist before calculating scores.")

    answered = {}
    sessions = db.execute(
        select(QuestionnaireSession.participant_id, QuestionnaireSession.questionnaire_id)
        .where(
            QuestionnaireSession.questionnaire_id.in_(questionnaire_ids),
            (QuestionnaireSession.ended_at.is_not(None))
            | select(Response.id).where(
                Response.session_id == QuestionnaireSession.id
            ).exists(),
        )
    )
    for participant_id, questionnaire_id in sessions:
        answered.setdefault(participant_id, set()).add(questionnaire_id)
    return {participant_id for participant_id, forms in answered.items() if len(forms) == 2}


# Input: db - an open database session; apply - True to stage changes, False to preview.
# Output: a dictionary of eligible_participants, new, updated, unchanged, and null_scores counts.
# Changes are staged only when apply=True; this function does not commit them.
def populate_scores(db, apply=False):
    """Stage scores without committing; missing required answers produce NULL."""
    eligible = answered_both_participants(db)
    participants = db.scalars(select(Participant).order_by(Participant.id)).all()
    rules = db.scalars(select(QuestionnaireScoringRule).where(
        QuestionnaireScoringRule.is_enabled.is_(True),
        QuestionnaireScoringRule.rule_type.in_(("total", "subscale")),
        QuestionnaireScoringRule.scoring_method.in_(("sum", "average")),
    )).all()
    questions = {}
    for link in db.scalars(select(ScoringRuleQuestion)):
        questions.setdefault(link.rule_id, []).append(link.question_id)

    answers = {}
    responses = db.execute(
        select(QuestionnaireSession.participant_id, QuestionVariant.canonical_question_id,
               Response.value_numeric, Response.value_text)
        .select_from(Response)
        .join(QuestionnaireSession, Response.session_id == QuestionnaireSession.id)
        .join(QuestionVariant, Response.question_variant_id == QuestionVariant.id)
        .order_by(Response.id)
    )
    for participant_id, question_id, numeric, text in responses:
        if participant_id in eligible:
            value = numeric if numeric is not None else text
            if value is not None and value != "":
                answers.setdefault((participant_id, question_id), value)

    existing = {
        (row.subject_id, row.rule_id): row
        for row in db.scalars(select(ParticipantTestScores))
    }
    counts = {"eligible_participants": len(eligible), "new": 0, "updated": 0,
              "unchanged": 0, "null_scores": 0}
    for participant in participants:
        if participant.id not in eligible:
            continue
        for rule in rules:
            values = [answers.get((participant.id, q)) for q in questions.get(rule.id, [])]
            score = None
            if values and all(isinstance(value, (int, float)) for value in values):
                result = sum(values)
                if rule.scoring_method == "average":
                    result /= len(values)
                score = Decimal(str(round(result, 2)))
            if score is None:
                counts["null_scores"] += 1
            previous = existing.get((participant.subject_id, rule.id))
            if previous is None:
                counts["new"] += 1
                if apply:
                    db.add(ParticipantTestScores(
                        subject_id=participant.subject_id, rule_id=rule.id, score=score,
                    ))
            elif previous.score != score:
                counts["updated"] += 1
                if apply:
                    previous.score = score
            else:
                counts["unchanged"] += 1
    return counts


# Input: no arguments; reads the APPLY setting and configured database connection.
# Output: prints counts and returns None; commits if APPLY=True, otherwise rolls back.
def main():
    from app.database.connection import SessionLocal

    with SessionLocal() as db:
        try:
            counts = populate_scores(db, apply=APPLY)
            for name, count in counts.items():
                print(f"{name}: {count}")
            if APPLY:
                db.commit()
                print("Scores saved.")
            else:
                db.rollback()
                print("Preview only. Set APPLY = True to save scores.")
        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()

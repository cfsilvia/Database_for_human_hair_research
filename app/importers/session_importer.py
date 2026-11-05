
import pandas as pd
from sqlalchemy import select

from app.database.models import (
    Participant,
    Questionnaire,
    QuestionnaireSession,
)


def get_questionnaire(db, questionnaire_code):

    return db.scalar(
        select(Questionnaire).where(
            Questionnaire.code == questionnaire_code
        )
    )


def session_exists(db, participant_id, questionnaire_id):

    return db.scalar(
        select(QuestionnaireSession).where(
            QuestionnaireSession.participant_id == participant_id,
            QuestionnaireSession.questionnaire_id == questionnaire_id,
        )
    )


def get_wording_form(value):

    if pd.isna(value):
        return None

    try:
        value = float(value)
    except (ValueError, TypeError):
        return None

    if value == 0:
        return "male"

    if value == 1:
        return "female"

    return None


def import_sessions(
    db,
    df: pd.DataFrame,
    questionnaire_code: str,
    subject_id_column: str = "subject id",
    started_column: str = "started",
    ended_column: str = "ended",
    score_column: str = "score",
):

    questionnaire = get_questionnaire(db, questionnaire_code)

    if questionnaire is None:
        raise ValueError(
            f"Questionnaire not found: {questionnaire_code}"
        )

    wording_questions = {
        "first-questionnaire": "Q3",
        "second-questionnaire": "Q2",
    }

    wording_column = wording_questions.get(questionnaire_code)

    if wording_column is None:
        raise ValueError(
            f"Unknown questionnaire: {questionnaire_code}"
        )

    for column in (subject_id_column, wording_column):
        if column not in df.columns:
            raise ValueError(f"Missing column: {column}")

    created = 0
    existing = 0
    skipped = 0
    missing_wording = 0

    created_session_ids = []

    for _, row in df.iterrows():

        subject_id = row[subject_id_column]

        if pd.isna(subject_id):
            print(
        f"SKIPPED SESSION: Missing Subject ID "
        f"at DataFrame row {row.name}, "
        f"Excel row approximately {row.name + 2}"
    )
            skipped += 1
            continue

        subject_id = int(subject_id)

        participant = db.scalar(
            select(Participant).where(
                Participant.subject_id == subject_id
            )
        )

        if participant is None:
            print(
                        f"SKIPPED SESSION: Participant not found, "
                        f"Subject ID = {subject_id}"
                    )
            skipped += 1
            continue

        # Check the participant AND the questionnaire
        existing_session = session_exists(
            db,
            participant.id,
            questionnaire.id,
        )

        # Never update an existing session
        if existing_session is not None:
            existing += 1
            continue

        wording_form = get_wording_form(
            row[wording_column]
        )

        if wording_form is None:
            missing_wording += 1
            skipped += 1
            continue

        started_at = row.get(started_column)
        ended_at = row.get(ended_column)
        score = row.get(score_column)

        if pd.isna(started_at):
            started_at = None

        if pd.isna(ended_at):
            ended_at = None

        if pd.isna(score):
            score = None

        session = QuestionnaireSession(
            participant_id=participant.id,
            questionnaire_id=questionnaire.id,
            wording_form=wording_form,
            started_at=started_at,
            ended_at=ended_at,
            score=score,
        )

        db.add(session)
        db.flush()

        created_session_ids.append(session.id)
        created += 1

    # The calling script is responsible for db.commit()

    return {
        "created": created,
        "existing": existing,
        "skipped": skipped,
        "missing_wording": missing_wording,
        "created_session_ids": created_session_ids,
    }

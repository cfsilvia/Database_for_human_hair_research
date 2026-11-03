import pandas as pd
from sqlalchemy import select

from app.database.models import (
    Participant,
    Questionnaire,
    QuestionnaireSession,
)


# ============================================================
# 1. FIND QUESTIONNAIRE
# ============================================================

def get_questionnaire(db, questionnaire_code: str):

    return db.scalar(
        select(Questionnaire).where(
            Questionnaire.code == questionnaire_code
        )
    )


# ============================================================
# 2. FIND EXISTING SESSION
# ============================================================

def session_exists(
    db,
    participant_id: int,
    questionnaire_id: int,
):

    return db.scalar(
        select(QuestionnaireSession).where(
            QuestionnaireSession.participant_id == participant_id,
            QuestionnaireSession.questionnaire_id == questionnaire_id,
        )
    )


# ============================================================
# 3. CONVERT WORDING PREFERENCE
#
# Both questionnaires:
# 0 = male wording
# 1 = female wording
# ============================================================

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


# ============================================================
# 4. IMPORT OR UPDATE QUESTIONNAIRE SESSIONS
# ============================================================

def import_sessions(
    db,
    df: pd.DataFrame,
    questionnaire_code: str,
    subject_id_column: str = "subject id",
    started_column: str = "started",
    ended_column: str = "ended",
    score_column: str = "score",
):

    # --------------------------------------------------------
    # Find questionnaire
    # --------------------------------------------------------

    questionnaire = get_questionnaire(
        db,
        questionnaire_code,
    )

    if questionnaire is None:
        raise ValueError(
            f"Questionnaire '{questionnaire_code}' "
            f"not found in database."
        )

    # --------------------------------------------------------
    # Identify wording-preference question
    # --------------------------------------------------------

    wording_question = {
        "first-questionnaire": "Q3",
        "second-questionnaire": "Q2",
    }

    wording_column = wording_question.get(
        questionnaire_code
    )

    if wording_column is None:
        raise ValueError(
            f"Unknown questionnaire: {questionnaire_code}"
        )

    if wording_column not in df.columns:
        raise ValueError(
            f"Wording column '{wording_column}' "
            f"not found in questionnaire DataFrame."
        )

    if subject_id_column not in df.columns:
        raise ValueError(
            f"Subject ID column '{subject_id_column}' "
            f"not found in questionnaire DataFrame."
        )

    # --------------------------------------------------------
    # Counters
    # --------------------------------------------------------

    created = 0
    existing = 0
    updated = 0
    skipped = 0
    missing_wording = 0

    # --------------------------------------------------------
    # Loop over questionnaire rows
    # --------------------------------------------------------

    for _, row in df.iterrows():

        subject_id = row[subject_id_column]

        if pd.isna(subject_id):
            skipped += 1
            continue

        subject_id = int(subject_id)

        # ----------------------------------------------------
        # Find participant
        # ----------------------------------------------------

        participant = db.scalar(
            select(Participant).where(
                Participant.subject_id == subject_id
            )
        )

        if participant is None:
            skipped += 1
            continue

        # ----------------------------------------------------
        # Read wording preference from Excel
        # ----------------------------------------------------

        wording_form = get_wording_form(
            row[wording_column]
        )

        if wording_form is None:
            missing_wording += 1

        # ----------------------------------------------------
        # Find existing session
        # ----------------------------------------------------

        existing_session = session_exists(
            db=db,
            participant_id=participant.id,
            questionnaire_id=questionnaire.id,
        )

        # ----------------------------------------------------
        # UPDATE EXISTING SESSION
        # ----------------------------------------------------

        if existing_session is not None:

            existing += 1

            if (
                wording_form is not None
                and existing_session.wording_form != wording_form
            ):

                existing_session.wording_form = wording_form
                updated += 1

            continue

        # ----------------------------------------------------
        # CREATE NEW SESSION
        # ----------------------------------------------------

        started_at = row.get(started_column)
        ended_at = row.get(ended_column)
        score = row.get(score_column)

        # Convert pandas missing values to SQL NULL
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

        created += 1

    # --------------------------------------------------------
    # Save changes
    # --------------------------------------------------------

    db.commit()

    return {
        "created": created,
        "existing": existing,
        "updated": updated,
        "skipped": skipped,
        "missing_wording": missing_wording,
    }
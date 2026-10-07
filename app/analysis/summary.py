from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database.models import (
    Participant,
    Questionnaire,
    QuestionnaireSession,
    QuestionVariant,
    Response,
)


# ============================================================
# GET ANSWERED RESPONSE ROWS
# ============================================================

def get_summary_rows(db: Session):

    rows = db.execute(
        select(
            Participant.subject_id,
            Questionnaire.code,
            QuestionVariant.gender_form,
            Response.value_numeric,
            Response.value_text,
        )
        .select_from(Response)

        .join(
            QuestionnaireSession,
            Response.session_id
            == QuestionnaireSession.id,
        )

        .join(
            Participant,
            QuestionnaireSession.participant_id
            == Participant.id,
        )

        .join(
            Questionnaire,
            QuestionnaireSession.questionnaire_id
            == Questionnaire.id,
        )

        .join(
            QuestionVariant,
            Response.question_variant_id
            == QuestionVariant.id,
        )

        # Keep only rows with an actual answer
        .where(
            or_(
                Response.value_numeric.is_not(None),

                (
                    Response.value_text.is_not(None)
                    & (Response.value_text != "")
                ),
            )
        )

    ).all()

    return rows


# ============================================================
# COUNT UNIQUE PARTICIPANTS
# ============================================================

def count_unique_participants(rows):

    subject_ids = {
        row.subject_id
        for row in rows
    }

    return len(subject_ids)


# ============================================================
# COUNT MALES AND FEMALES
# ============================================================

def count_gender(
    db: Session,
):

    rows = db.execute(
        select(
            Participant.subject_id,
            Questionnaire.code,
            QuestionVariant.question_number,
            QuestionVariant.id.label(
                "question_variant_id"
            ),
            Response.value_numeric,
        )

        .select_from(Response)

        .join(
            QuestionVariant,
            Response.question_variant_id
            == QuestionVariant.id,
        )

        .join(
            QuestionnaireSession,
            Response.session_id
            == QuestionnaireSession.id,
        )

        .join(
            Participant,
            QuestionnaireSession.participant_id
            == Participant.id,
        )

        .join(
            Questionnaire,
            QuestionVariant.questionnaire_id
            == Questionnaire.id,
        )

        .where(
            QuestionVariant.question
            == "מין בעת הלידה",

            Response.value_numeric.in_(
                [0, 1]
            ),
        )

    ).all()


    male_subjects = {
        row.subject_id
        for row in rows
        if row.value_numeric == 1
    }


    female_subjects = {
        row.subject_id
        for row in rows
        if row.value_numeric == 0
    }


    return {
        "males": len(male_subjects),
        "females": len(female_subjects),
    }
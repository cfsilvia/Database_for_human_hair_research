from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.analysis.summary import get_summary_rows, count_unique_participants, count_gender
from app.database.dependencies import get_db
from app.database.models import (
    Participant,
    Questionnaire,
    QuestionnaireSession,
    QuestionVariant,
    CanonicalQuestion,
    Response,
)


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


# ---------------------------------------------------------
# FASTAPI APPLICATION
# ---------------------------------------------------------

app = FastAPI(
    title="Hair Research Database"
)


# ---------------------------------------------------------
# STATIC FILES
# ---------------------------------------------------------

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


# ---------------------------------------------------------
# HOMEPAGE
# ---------------------------------------------------------

@app.get("/")
def home():
    return FileResponse(
        STATIC_DIR / "index.html"
    )


# ---------------------------------------------------------
# PARTICIPANT API
# ---------------------------------------------------------

@app.get("/api/participants/{subject_id}")
def get_participant(
    subject_id: int,
    db: Session = Depends(get_db),
):
    participant = db.scalar(
        select(Participant).where(
            Participant.subject_id == subject_id
        )
    )

    if participant is None:
        raise HTTPException(
            status_code=404,
            detail="Participant not found",
        )

    return {
        "id": participant.id,
        "subject_id": participant.subject_id,
    }
    
    #Responses
@app.get("/api/participants/{subject_id}/responses")
def get_participant_responses(
    subject_id: int,
    db: Session = Depends(get_db),
):
    participant = db.scalar(
        select(Participant).where(
            Participant.subject_id == subject_id
        )
    )

    if participant is None:
        raise HTTPException(
            status_code=404,
            detail="Participant not found",
        )

    rows = db.execute(
        select(
            Questionnaire.code.label("questionnaire"),
            CanonicalQuestion.test_psicolog.label("test"),
            QuestionVariant.gender_form.label("gender_form"),
            QuestionVariant.question_number.label("question_number"),
            QuestionVariant.parent_question_number.label(
                "parent_question_number"
            ),
            QuestionVariant.parent_question.label(
                "parent_question"
            ),
            QuestionVariant.question.label("question"),
            Response.value_numeric.label("value_numeric"),
            Response.value_text.label("value_text"),
        )
        .select_from(QuestionnaireSession)

        .join(
            Questionnaire,
            QuestionnaireSession.questionnaire_id
            == Questionnaire.id,
        )

        .join(
            Response,
            Response.session_id
            == QuestionnaireSession.id,
        )

        .join(
            QuestionVariant,
            Response.question_variant_id
            == QuestionVariant.id,
        )

        .join(
            CanonicalQuestion,
            QuestionVariant.canonical_question_id
            == CanonicalQuestion.id,
        )

        .where(
            QuestionnaireSession.participant_id
            == participant.id
        )
    ).all()

    responses = []

    for row in rows:
        responses.append(
            {
                "questionnaire": row.questionnaire,
                "test": row.test,
                "gender_form": row.gender_form,
                "question_number": row.question_number,
                "parent_question_number":
                    row.parent_question_number,
                "parent_question":
                    row.parent_question,
                "question": row.question,
                "value_numeric": row.value_numeric,
                "value_text": row.value_text,
            }
        )

    return {
        "subject_id": participant.subject_id,
        "responses": responses,
    }
    
@app.get("/api/summary-test")
def summary_test(
    db: Session = Depends(get_db),
):
    rows = get_summary_rows(db)
    unique_participants = count_unique_participants(rows)
    gender_counts = count_gender(db)

    return {
        "row_count": len(rows),
         "participants": unique_participants,
         "males": gender_counts["males"],
        "females": gender_counts["females"],
    }

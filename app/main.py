from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
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


@app.get("/api/participants-table")
def get_participants_table(db: Session = Depends(get_db)):
    """One row per subject; columns grouped by test and canonical question."""
    fixed_columns = [
        {"key": "questionnaire_1_started_at", "label": "Questionnaire 1 begin"},
        {"key": "questionnaire_1_ended_at", "label": "Questionnaire 1 end"},
        {"key": "questionnaire_2_started_at", "label": "Questionnaire 2 begin"},
        {"key": "questionnaire_2_ended_at", "label": "Questionnaire 2 end"},
        {"key": "answered_questionnaire_1", "label": "Answered questionnaire 1"},
        {"key": "answered_questionnaire_2", "label": "Answered questionnaire 2"},
        {"key": "answered_both_questionnaires", "label": "Answered both questionnaires"},
    ]

    questionnaires = db.execute(
        select(Questionnaire.id, Questionnaire.code).order_by(Questionnaire.id)
    ).all()
    number_by_id = {}
    preferred = {"first-questionnaire": 1, "second-questionnaire": 2}
    used = set()
    for q in questionnaires:
        n = preferred.get(q.code)
        if n is not None and n not in used:
            number_by_id[q.id] = n
            used.add(n)
    for q in questionnaires:
        if q.id not in number_by_id:
            n = 1
            while n in used:
                n += 1
            number_by_id[q.id] = n
            used.add(n)

    # One column per canonical ID. Male and female variants of the same
    # canonical question automatically share the same output column.
    questions = db.execute(
        select(
            CanonicalQuestion.id.label("canonical_id"),
            CanonicalQuestion.questionnaire_id,
            CanonicalQuestion.test_psicolog,
            CanonicalQuestion.code,
            CanonicalQuestion.item_order,
            QuestionVariant.gender_form,
            QuestionVariant.question_number,
            QuestionVariant.question,
            QuestionVariant.parent_question,
        )
        .outerjoin(
            QuestionVariant,
            QuestionVariant.canonical_question_id == CanonicalQuestion.id,
        )
        .order_by(
            CanonicalQuestion.test_psicolog,
            CanonicalQuestion.item_order,
            CanonicalQuestion.id,
            QuestionVariant.id,
        )
    ).all()

    def is_demographic(name):
        return "DEMOG_HEALTH" in str(name or "").upper().replace("-", "_").replace(" ", "_")

    question_by_id = {}
    for q in questions:
        if q.canonical_id not in question_by_id:
            question_by_id[q.canonical_id] = q
        elif q.gender_form == "male":
            # Prefer male wording for shared headings, as in the original UI.
            question_by_id[q.canonical_id] = q

    grouped = {}
    ordered_questions = sorted(
        question_by_id.values(),
        key=lambda q: (
            not is_demographic(q.test_psicolog),
            str(q.test_psicolog or "Unknown"),
            q.item_order if q.item_order is not None else 999999,
            number_by_id.get(q.questionnaire_id, 999),
            q.canonical_id,
        ),
    )
    for q in ordered_questions:
        test = q.test_psicolog or "Unknown"
        # Group by TEST, not questionnaire: a test can span both forms.
        group = grouped.setdefault(test, {"test": test, "columns": []})
        full_question = "\n\n".join(
            str(x) for x in (q.parent_question, q.question) if x
        )
        if is_demographic(test) and all(
            token in full_question for token in ("הזינו", "מספר", "שקיבלת")
        ):
            continue
        questionnaire_number = number_by_id.get(q.questionnaire_id, 3)
        tooltip = f"Questionnaire {questionnaire_number}"
        if q.question_number:
            tooltip += f"\nQuestion {q.question_number}"
        group["columns"].append({
            "key": f"canonical_{q.canonical_id}",
            "label": q.question or q.parent_question or q.code,
            "tooltip": tooltip,
            "questionnaire_number": questionnaire_number,
            "question_number": q.question_number,
            "question": q.question,
            "parent_question": q.parent_question,
        })
    groups = list(grouped.values())

    participants = db.scalars(
        select(Participant).order_by(Participant.subject_id)
    ).all()
    rows = []
    by_participant_id = {}
    for participant in participants:
        row = {"subject_id": participant.subject_id}
        for col in fixed_columns:
            row[col["key"]] = "No" if col["key"].startswith("answered_") else ""
        for group in groups:
            for col in group["columns"]:
                row[col["key"]] = ""
        rows.append(row)
        by_participant_id[participant.id] = row

    # Session dates and completion flags remain separate from answer pivoting.
    sessions = db.execute(
        select(
            QuestionnaireSession.participant_id,
            QuestionnaireSession.questionnaire_id,
            func.min(QuestionnaireSession.started_at).label("started_at"),
            func.max(QuestionnaireSession.ended_at).label("ended_at"),
            func.count(Response.id).label("response_count"),
        )
        .select_from(QuestionnaireSession)
        .outerjoin(Response, Response.session_id == QuestionnaireSession.id)
        .group_by(
            QuestionnaireSession.participant_id,
            QuestionnaireSession.questionnaire_id,
        )
    ).all()
    for session in sessions:
        row = by_participant_id.get(session.participant_id)
        n = number_by_id.get(session.questionnaire_id)
        if row is None or n not in (1, 2):
            continue
        prefix = f"questionnaire_{n}"
        row[f"{prefix}_started_at"] = (
            session.started_at.isoformat() if session.started_at else ""
        )
        row[f"{prefix}_ended_at"] = (
            session.ended_at.isoformat() if session.ended_at else ""
        )
        if session.response_count > 0 or session.ended_at is not None:
            row[f"answered_{prefix}"] = "Yes"

    for row in rows:
        if (row["answered_questionnaire_1"] == "Yes"
                and row["answered_questionnaire_2"] == "Yes"):
            row["answered_both_questionnaires"] = "Yes"

    # Simple long-format query, sorted by participant and test; pivot to cells.
    answers = db.execute(
        select(
            Response.id,
            QuestionnaireSession.participant_id,
            CanonicalQuestion.id.label("canonical_id"),
            CanonicalQuestion.test_psicolog,
            Response.value_numeric,
            Response.value_text,
        )
        .join(QuestionnaireSession, Response.session_id == QuestionnaireSession.id)
        .join(QuestionVariant, Response.question_variant_id == QuestionVariant.id)
        .join(CanonicalQuestion, QuestionVariant.canonical_question_id == CanonicalQuestion.id)
        .order_by(
            QuestionnaireSession.participant_id,
            CanonicalQuestion.test_psicolog,
            CanonicalQuestion.item_order,
            Response.id,
        )
    ).all()
    for answer in answers:
        row = by_participant_id.get(answer.participant_id)
        key = f"canonical_{answer.canonical_id}"
        if row is None or key not in row:
            continue
        value = (answer.value_numeric if answer.value_numeric is not None
                 else answer.value_text)
        if value is not None and value != "" and row[key] == "":
            row[key] = value

    return {"fixed_columns": fixed_columns, "groups": groups, "rows": rows}

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
def get_participants_table(
    db: Session = Depends(get_db),
):
    preferred_questionnaire_numbers = {
        "first-questionnaire": 1,
        "second-questionnaire": 2,
    }

    questionnaire_rows = db.execute(
        select(Questionnaire.code).order_by(
            Questionnaire.id
        )
    ).all()

    questionnaire_number_by_code = {}
    used_questionnaire_numbers = set()

    for questionnaire in questionnaire_rows:
        number = preferred_questionnaire_numbers.get(
            questionnaire.code
        )

        if number is None or number in used_questionnaire_numbers:
            continue

        questionnaire_number_by_code[questionnaire.code] = number
        used_questionnaire_numbers.add(number)

    next_questionnaire_number = 1

    for questionnaire in questionnaire_rows:
        if questionnaire.code in questionnaire_number_by_code:
            continue

        while next_questionnaire_number in used_questionnaire_numbers:
            next_questionnaire_number += 1

        questionnaire_number_by_code[
            questionnaire.code
        ] = next_questionnaire_number
        used_questionnaire_numbers.add(next_questionnaire_number)

    fixed_columns = [
        {
            "key": "questionnaire_1_started_at",
            "label": "Questionnaire 1 begin",
        },
        {
            "key": "questionnaire_1_ended_at",
            "label": "Questionnaire 1 end",
        },
        {
            "key": "questionnaire_2_started_at",
            "label": "Questionnaire 2 begin",
        },
        {
            "key": "questionnaire_2_ended_at",
            "label": "Questionnaire 2 end",
        },
        {
            "key": "answered_questionnaire_1",
            "label": "Answered questionnaire 1",
        },
        {
            "key": "answered_questionnaire_2",
            "label": "Answered questionnaire 2",
        },
        {
            "key": "answered_both_questionnaires",
            "label": "Answered both questionnaires",
        },
    ]

    def has_value(value):
        return value is not None and value != ""

    def format_datetime(value):
        if value is None:
            return ""

        return value.isoformat()

    def is_demog_health(test_name):
        normalized = (
            str(test_name or "")
            .upper()
            .replace("-", "_")
            .replace(" ", "_")
        )

        return "DEMOG_HEALTH" in normalized

    def format_question_label(question, parent_question):
        if question:
            return question

        if parent_question:
            return parent_question

        return None

    def format_question_tooltip(question, parent_question):
        if question and parent_question:
            return f"{parent_question}\n\n{question}"

        return format_question_label(
            question,
            parent_question,
        )

    def format_question_reference(
        questionnaire_number,
        question_number,
    ):
        reference = f"Questionnaire {questionnaire_number}"

        if question_number:
            return f"{reference}\nQuestion {question_number}"

        return reference

    def should_hide_participants_column(test_name, label):
        if not is_demog_health(test_name):
            return False

        normalized_label = str(label or "")

        return (
            "הזינו" in normalized_label
            and "מספר" in normalized_label
            and "שקיבלת" in normalized_label
        )

    male_variant_rows = db.execute(
        select(
            QuestionVariant.canonical_question_id,
            QuestionVariant.question_number,
            QuestionVariant.question,
            QuestionVariant.parent_question,
        )
        .where(
            QuestionVariant.gender_form == "male"
        )
        .order_by(
            QuestionVariant.canonical_question_id,
            QuestionVariant.id,
        )
    ).all()

    male_question_numbers_by_canonical_id = {}
    male_questions_by_canonical_id = {}
    male_parent_questions_by_canonical_id = {}

    for variant in male_variant_rows:
        if (
            variant.canonical_question_id
            in male_question_numbers_by_canonical_id
        ):
            continue

        male_question_numbers_by_canonical_id[
            variant.canonical_question_id
        ] = variant.question_number
        male_questions_by_canonical_id[
            variant.canonical_question_id
        ] = variant.question
        male_parent_questions_by_canonical_id[
            variant.canonical_question_id
        ] = variant.parent_question

    canonical_rows = db.execute(
        select(
            CanonicalQuestion.id,
            Questionnaire.code.label("questionnaire_code"),
            CanonicalQuestion.test_psicolog,
            CanonicalQuestion.code,
            CanonicalQuestion.item_order,
        )
        .join(
            Questionnaire,
            CanonicalQuestion.questionnaire_id
            == Questionnaire.id,
        )
        .order_by(
            Questionnaire.code,
            CanonicalQuestion.test_psicolog,
            CanonicalQuestion.item_order,
            CanonicalQuestion.code,
        )
    ).all()

    groups_by_test = {}

    for canonical in canonical_rows:
        test_name = canonical.test_psicolog or "Unknown"
        group_key = (
            canonical.questionnaire_code,
            test_name,
        )

        questionnaire_number = (
            questionnaire_number_by_code.get(
                canonical.questionnaire_code,
                3,
            )
        )

        if group_key not in groups_by_test:
            groups_by_test[group_key] = {
                "test": test_name,
                "is_demographic": is_demog_health(test_name),
                "questionnaire_order": questionnaire_number,
                "columns": [],
            }

        question_number = male_question_numbers_by_canonical_id.get(
            canonical.id
        )
        question = male_questions_by_canonical_id.get(
            canonical.id
        )
        parent_question = male_parent_questions_by_canonical_id.get(
            canonical.id
        )
        label = (
            format_question_label(
                question,
                parent_question,
            )
            or canonical.code
        )
        tooltip = format_question_reference(
            questionnaire_number,
            question_number,
        )
        full_question_text = (
            format_question_tooltip(
                question,
                parent_question,
            )
            or canonical.code
        )

        if should_hide_participants_column(test_name, full_question_text):
            continue

        groups_by_test[group_key]["columns"].append(
            {
                "key": f"canonical_{canonical.id}",
                "label": label,
                "tooltip": tooltip,
                "questionnaire_number": questionnaire_number,
                "question_number": question_number,
                "question": question,
                "parent_question": parent_question,
            }
        )

    groups = sorted(
        groups_by_test.values(),
        key=lambda group: (
            not group["is_demographic"],
            group["questionnaire_order"],
            group["test"],
        ),
    )

    for group in groups:
        group.pop("is_demographic", None)
        group.pop("questionnaire_order", None)

    all_columns = [
        column
        for group in groups
        for column in group["columns"]
    ]

    participants = db.scalars(
        select(Participant).order_by(
            Participant.subject_id
        )
    ).all()

    rows = []
    rows_by_subject_id = {}

    for participant in participants:
        row = {
            "subject_id": participant.subject_id,
            "questionnaire_1_started_at": "",
            "questionnaire_1_ended_at": "",
            "questionnaire_2_started_at": "",
            "questionnaire_2_ended_at": "",
            "answered_questionnaire_1": "No",
            "answered_questionnaire_2": "No",
            "answered_both_questionnaires": "No",
        }

        for column in all_columns:
            row[column["key"]] = ""

        rows.append(row)
        rows_by_subject_id[participant.id] = row

    session_rows = db.execute(
        select(
            Participant.id.label("participant_id"),
            Questionnaire.code.label("questionnaire_code"),
            func.min(
                QuestionnaireSession.started_at
            ).label("started_at"),
            func.max(
                QuestionnaireSession.ended_at
            ).label("ended_at"),
            func.count(Response.id).label("response_count"),
        )
        .select_from(QuestionnaireSession)
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
        .outerjoin(
            Response,
            Response.session_id
            == QuestionnaireSession.id,
        )
        .group_by(
            Participant.id,
            Questionnaire.code,
        )
    ).all()

    for session in session_rows:
        row = rows_by_subject_id.get(
            session.participant_id
        )

        if row is None:
            continue

        questionnaire_number = questionnaire_number_by_code.get(
            session.questionnaire_code
        )

        if questionnaire_number not in (1, 2):
            continue

        prefix = f"questionnaire_{questionnaire_number}"

        row[f"{prefix}_started_at"] = format_datetime(
            session.started_at
        )
        row[f"{prefix}_ended_at"] = format_datetime(
            session.ended_at
        )

        if session.response_count > 0 or session.ended_at is not None:
            row[f"answered_{prefix}"] = "Yes"

    for row in rows:
        if (
            row["answered_questionnaire_1"] == "Yes"
            and row["answered_questionnaire_2"] == "Yes"
        ):
            row["answered_both_questionnaires"] = "Yes"

    answer_rows = db.execute(
        select(
            Participant.id.label("participant_id"),
            CanonicalQuestion.id.label("canonical_id"),
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
        .join(
            CanonicalQuestion,
            QuestionVariant.canonical_question_id
            == CanonicalQuestion.id,
        )
        .order_by(
            Participant.subject_id,
            Questionnaire.code,
            CanonicalQuestion.test_psicolog,
            CanonicalQuestion.item_order,
        )
    ).all()

    for answer in answer_rows:
        row = rows_by_subject_id.get(
            answer.participant_id
        )

        if row is None:
            continue

        if answer.value_numeric is not None:
            value = answer.value_numeric
        elif answer.value_text is not None:
            value = answer.value_text
        else:
            value = ""

        if not has_value(value):
            continue

        key = f"canonical_{answer.canonical_id}"

        if not has_value(row.get(key)):
            row[key] = value

    return {
        "fixed_columns": fixed_columns,
        "groups": groups,
        "rows": rows,
    }

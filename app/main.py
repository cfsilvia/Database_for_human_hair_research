from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.auth import require_login, router as auth_router
from app.participants_export import router as participants_export_router
from app.analysis.summary import get_participation_summary
from app.database.dependencies import get_db
from app.database.models import (
    Participant,
    ParticipantTestScores,
    Questionnaire,
    QuestionnaireSession,
    QuestionVariant,
    CanonicalQuestion,
    Response,
    ResponseValueLabel,
    QuestionnaireScoringRule,
    WarPeriod,
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

app.middleware("http")(require_login)
app.include_router(auth_router)
app.include_router(participants_export_router)


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
    summary = get_participation_summary(db)

    return {
        **summary,
        "participants": summary["answered_any"],
        "males": summary["males_both"],
        "females": summary["females_both"],
    }


'''
Input: score is a numeric score or None. rules contains enabled interpretation
rules linked to that score, with range_min, range_max, and interpretation_he.
Output: the Hebrew interpretation when exactly one range matches (including
both boundaries), or None when the score is missing or no unique range matches.
'''
def get_score_interpretation(score, rules):
    if score is None:
        return None

    matches = [
        rule
        for rule in rules
        if rule.range_min is not None
        and rule.range_max is not None
        and rule.range_min <= score <= rule.range_max
    ]

    if len(matches) != 1:
        return None

    return matches[0].interpretation_he


'''
Input: db is the active SQLAlchemy database session.
Output: a dictionary mapping each parent score-rule ID to its enabled
interpretation rules.
'''
def get_interpretation_rules(db):
    rules = db.scalars(
        select(QuestionnaireScoringRule).where(
            QuestionnaireScoringRule.is_enabled.is_(True),
            QuestionnaireScoringRule.rule_type == "interpretation",
            QuestionnaireScoringRule.parent_rule_id.is_not(None),
        )
    ).all()

    rules_by_parent = {}
    for rule in rules:
        rules_by_parent.setdefault(rule.parent_rule_id, []).append(rule)

    return rules_by_parent

#############################################################

def israel_date(value):
    """Return the Israel calendar date; assume naive timestamps are Israel time."""
    if value is None:
        return None

    if value.tzinfo is not None:
        value = value.astimezone(ZoneInfo("Asia/Jerusalem"))

    return value.date()


def get_session_war(started_at, ended_at, war_periods):
    """Return wars overlapping the answering dates, or No war/Unknown."""
    start = israel_date(started_at)
    end = israel_date(ended_at)

    if start and end and end < start:
        return "Unknown"

    matches = []

    for war in war_periods:
        if start is not None and end is not None:
            overlaps = start <= war.end_date and end >= war.start_date
        else:
            # One known date inside a war is enough to confirm overlap.
            known_date = start if start is not None else end
            overlaps = (
                known_date is not None
                and war.start_date <= known_date <= war.end_date
            )

        if overlaps:
            matches.append(war.name)

    if matches:
        return ", ".join(matches)

    if start is None or end is None:
        return "Unknown"

    return "No war"
##################################################################

# Build the participants table with answers, total scores, and subscale scores.
@app.get("/api/participants-table")
def get_participants_table(db: Session = Depends(get_db)):
    """One row per subject; columns grouped by test and canonical question."""
    fixed_columns = [
        {"key": "questionnaire_1_started_at", "label": "Questionnaire 1 begin"},
        {"key": "questionnaire_1_ended_at", "label": "Questionnaire 1 end"},
        {"key": "questionnaire_1_war", "label": "Questionnaire 1 war"},
        {"key": "questionnaire_2_started_at", "label": "Questionnaire 2 begin"},
        {"key": "questionnaire_2_ended_at", "label": "Questionnaire 2 end"},
        {"key": "questionnaire_2_war", "label": "Questionnaire 2 war"},
        {"key": "answered_questionnaire_1", "label": "Answered questionnaire 1"},
        {"key": "answered_questionnaire_2", "label": "Answered questionnaire 2"},
        {"key": "answered_both_questionnaires", "label": "Answered both questionnaires"},
    ]

    questionnaires = db.execute(
        select(Questionnaire.id, Questionnaire.code)
    ).all()
    preferred = {"first-questionnaire": 1, "second-questionnaire": 2}
    number_by_id = {
        q.id: preferred[q.code]
        for q in questionnaires
        if q.code in preferred
    }

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
            "canonical_code": q.code,
            "label": q.question or q.parent_question or q.code,
            "tooltip": tooltip,
            "questionnaire_number": questionnaire_number,
            "question_number": q.question_number,
            "question": q.question,
            "parent_question": q.parent_question,
        })
    groups = list(grouped.values())

    # Load column definitions for total and subscale scores.
    scoring_rules = db.scalars(
        select(QuestionnaireScoringRule)
        .where(
            QuestionnaireScoringRule.is_enabled.is_(True),
            QuestionnaireScoringRule.rule_type.in_(("total", "subscale")),
            QuestionnaireScoringRule.scoring_method.in_(("sum", "average")),
        )
        .order_by(
            QuestionnaireScoringRule.test_name,
            QuestionnaireScoringRule.rule_code,
        )
    ).all()

    interpretation_rules = get_interpretation_rules(db)

    # Add total and subscale columns after each test's questions.
    for group in groups:
        test_rules = [
            rule for rule in scoring_rules
            if rule.test_name == group["test"]
        ]
        test_rules.sort(
            key=lambda rule: (rule.rule_type != "total", rule.rule_code)
        )
        total_count = sum(rule.rule_type == "total" for rule in test_rules)

        for rule in test_rules:
            if rule.rule_type == "total":
                label = "Total score"
                if total_count > 1:
                    label += f" ({rule.rule_code})"
            else:
                label = rule.subscale_name or rule.rule_code

            group["columns"].append({
                "key": f"score_{rule.id}",
                "label": label,
                "tooltip": f"{group['test']} - {label}",
                "description": rule.description_he,
                "scoring_method": rule.scoring_method,
                "min_score": rule.min_score,
                "max_score": rule.max_score,
                "missing_score_label": (
                    "No PCL answer"
                    if rule.test_name == "PCL" and rule.rule_type == "total"
                    else "Missing score"
                ),
                "interpretation_ranges": [
                    {"min": item.range_min, "max": item.range_max,
                     "label": item.interpretation_he}
                    for item in sorted(
                        interpretation_rules.get(rule.id, []),
                        key=lambda item: (item.range_min is None,
                                          item.range_min or 0, item.id),
                    )
                ],
            })

    participants = db.scalars(
        select(Participant).order_by(Participant.subject_id)
    ).all()
    rows = []
    by_participant_id = {}
    participant_wordings = {}
    for participant in participants:
        row = {"subject_id": participant.subject_id}
        for col in fixed_columns:
            row[col["key"]] = "No" if col["key"].startswith("answered_") else ""
        row["questionnaire_1_war"] = "Not answered"
        row["questionnaire_2_war"] = "Not answered"
        for group in groups:
            for col in group["columns"]:
                row[col["key"]] = ""
        rows.append(row)
        by_participant_id[participant.id] = row

    # Read war dates once for the whole participants table.
    war_periods = db.scalars(
        select(WarPeriod).order_by(WarPeriod.start_date)
    ).all()

    questionnaire_sessions = db.scalars(
        select(QuestionnaireSession)
    ).all()

    war_results = {}

    # Check each actual session separately to avoid counting gaps between sessions.
    for session in questionnaire_sessions:
        number = number_by_id.get(session.questionnaire_id)

        if number not in (1, 2):
            continue

        key = (session.participant_id, number)
        result = get_session_war(
            session.started_at,
            session.ended_at,
            war_periods,
        )

        war_results.setdefault(key, set()).update(result.split(", "))

    # Combine results when a participant has multiple sessions.
    for (participant_id, number), results in war_results.items():
        row = by_participant_id.get(participant_id)

        if row is None:
            continue

        names = [
            war.name for war in war_periods
            if war.name in results
        ]

        if names:
            value = ", ".join(names)
        elif "Unknown" in results:
            value = "Unknown"
        else:
            value = "No war"

        row[f"questionnaire_{number}_war"] = value

    # Session dates and completion flags remain separate from answer pivoting.
    answered_session = (
        QuestionnaireSession.ended_at.is_not(None) | Response.id.is_not(None)
    )
    sessions = db.execute(
        select(
            QuestionnaireSession.participant_id,
            QuestionnaireSession.questionnaire_id,
            func.min(QuestionnaireSession.started_at).label("started_at"),
            func.max(QuestionnaireSession.ended_at).label("ended_at"),
            func.count(Response.id).label("response_count"),
            func.min(QuestionnaireSession.wording_form).filter(answered_session).label("wording_min"),
            func.max(QuestionnaireSession.wording_form).filter(answered_session).label("wording_max"),
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
            wordings = participant_wordings.setdefault(session.participant_id, set())
            wordings.update(value for value in (session.wording_min, session.wording_max)
                            if value)

    for participant_id, row in by_participant_id.items():
        wordings = participant_wordings.get(participant_id, set())
        row["wording_form"] = next(iter(wordings)) if len(wordings) == 1 else (
            "mixed" if wordings else None
        )

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
            QuestionVariant.gender_form,
            ResponseValueLabel.text_male,
            ResponseValueLabel.text_female,
        )
        .join(QuestionnaireSession, Response.session_id == QuestionnaireSession.id)
        .join(QuestionVariant, Response.question_variant_id == QuestionVariant.id)
        .join(CanonicalQuestion, QuestionVariant.canonical_question_id == CanonicalQuestion.id)
        .outerjoin(
            ResponseValueLabel,
            (ResponseValueLabel.question_id == CanonicalQuestion.id)
            & (ResponseValueLabel.numeric_value == Response.value_numeric),
        )
        .order_by(
            QuestionnaireSession.participant_id,
            CanonicalQuestion.test_psicolog,
            CanonicalQuestion.item_order,
            Response.id,
        )
    ).all()
    answer_labels = {}
    for answer in answers:
        row = by_participant_id.get(answer.participant_id)
        key = f"canonical_{answer.canonical_id}"
        if row is None or key not in row:
            continue
        value = (answer.value_numeric if answer.value_numeric is not None
                 else answer.value_text)
        if value is not None and value != "" and row[key] == "":
            row[key] = value
            label = None
            if answer.gender_form == "male":
                label = answer.text_male
            elif answer.gender_form == "female":
                label = answer.text_female
            if answer.value_numeric is not None and label and label.strip():
                answer_labels.setdefault(str(row["subject_id"]), {})[key] = label

    score_interpretations = {}
    stored_scores = {
        (score.subject_id, score.rule_id): score.score
        for score in db.scalars(select(ParticipantTestScores))
    }

    # Read total and subscale scores for participants who answered both forms.
    for row in rows:
        if row["answered_both_questionnaires"] != "Yes":
            continue

        for rule in scoring_rules:
            score_key = f"score_{rule.id}"
            score = stored_scores.get((row["subject_id"], rule.id))

            if score_key not in row or score is None:
                continue

            score = float(score)
            interpretation = get_score_interpretation(
                score,
                interpretation_rules.get(rule.id, []),
            )
            row[score_key] = round(score, 2)

            if interpretation:
                subject_id = str(row["subject_id"])
                score_interpretations.setdefault(subject_id, {})[score_key] = interpretation

    return {
        "fixed_columns": fixed_columns,
        "groups": groups,
        "rows": rows,
        "answer_labels": answer_labels,
        "score_interpretations": score_interpretations,
    }

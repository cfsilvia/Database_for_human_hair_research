import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    CanonicalQuestion,
    Questionnaire,
    QuestionVariant,
)


def empty_to_none(value):
    if pd.isna(value):
        return None

    return value


def get_or_create_questionnaire(
    db: Session,
    code: str,
    name: str,
):
    questionnaire = db.scalar(
        select(Questionnaire).where(Questionnaire.code == code)
    )

    if questionnaire is None:
        questionnaire = Questionnaire(
            code=code,
            name=name,
        )

        db.add(questionnaire)
        db.flush()

    return questionnaire


def get_or_create_canonical_question(
    db: Session,
    code: str,
    test_psicolog: str,
    item_order: int,
):
    question = db.scalar(
        select(CanonicalQuestion).where(
            CanonicalQuestion.code == code
        )
    )

    if question is None:
        question = CanonicalQuestion(
            code=code,
            test_psicolog=test_psicolog,
            item_order=item_order,
        )

        db.add(question)
        db.flush()

    return question


def variant_exists(
    db: Session,
    questionnaire_id: int,
    file_name: str | None,
    question_number: str,
    gender_form: str,
    subquestion_phrase: str | None,
):
    return db.scalar(
        select(QuestionVariant).where(
            QuestionVariant.questionnaire_id
            == questionnaire_id,

            QuestionVariant.file_name
            == file_name,

            QuestionVariant.question_number
            == question_number,

            QuestionVariant.gender_form
            == gender_form,

            QuestionVariant.subquestion_phrase
            == subquestion_phrase,
        )
    )

# Only valid questions are taken into account.
def import_metadata(
    db: Session,
    df,
):
    imported = 0
    skipped = 0

    for _, row in df.iterrows():
        questionnaire = get_or_create_questionnaire(
            db=db,
            code=row["questionnaire"],
            name=row["questionnaire"],
        )

        canonical_question = get_or_create_canonical_question(
            db=db,
            code=row["canonical_question"],
            test_psicolog=row["file name"],
            item_order=int(row["item_order"]),
        )

        subquestion_phrase = empty_to_none(row.get("subquestion phrase"))

        existing = variant_exists(
            db=db,
            questionnaire_id=questionnaire.id,
            file_name=row["file name"],
            question_number=row["number question"],
            gender_form=row["gender_form"],
            subquestion_phrase=subquestion_phrase,
        )

        if existing:
            skipped += 1
            continue

        variant = QuestionVariant(
            questionnaire_id=questionnaire.id,
            canonical_question_id=canonical_question.id,
            question_number=row["number question"],
            question=row["question"],
            gender_form=row["gender_form"],
            file_name=row["file name"],
            subquestion_number=empty_to_none(
                row.get("subquestion number")
            ),
            subquestion_phrase=subquestion_phrase,
            pair_status=empty_to_none(row.get("pair_status")),
            pair_similarity=empty_to_none(row.get("pair_similarity")),
        )

        db.add(variant)
        imported += 1

    db.commit()

    return {
        "imported": imported,
        "skipped": skipped,
    }

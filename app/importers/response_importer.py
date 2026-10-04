import re

import pandas as pd
from sqlalchemy import select

from app.database.models import (
    Participant,
    Questionnaire,
    QuestionnaireSession,
    QuestionVariant,
    Response,
)

'''
Extract question number
'''
def extract_question_number(column_name):
    """
    Examples:
        Q12       -> Q12
        q12.1     -> Q12.1
        Q5.other  -> Q5.other
        Q13.detail -> Q13.detail
    """

    if not isinstance(column_name, str):
        return None

    value = column_name.strip()

    match = re.match(r"^(Q\d+(?:\.\d+|\.(?:other|detail))?)$", value, flags=re.IGNORECASE,)

    if match:
        value = match.group(1)

        # Only uppercase the Q
        return "Q" + value[1:]

    return None

'''
Determine if it is male or female
'''
def get_gender_question_numbers(db, questionnaire_id: int,):
    variants = db.scalars(
        select(QuestionVariant).where(QuestionVariant.questionnaire_id == questionnaire_id,
             QuestionVariant.question.contains("מין בעת הלידה"),)).all()

    return [variant.question_number for variant in variants]


def get_gender_form(row, gender_columns):
    if not gender_columns:
        return None

    for column in gender_columns:
        value = row[column]

        if pd.isna(value):
            continue

        if value == 1:
            return "male"

        if value == 0:
            return "female"

    return None


'''
Find the session for the participant
'''
def get_session(db, subject_id: int, questionnaire_code: str,):
    questionnaire = db.scalar(
        select(Questionnaire).where(
            Questionnaire.code == questionnaire_code
        )
    )

    if questionnaire is None:
        raise ValueError(
            f"Questionnaire not found: {questionnaire_code}"
        )

    participant = db.scalar(
        select(Participant).where(
            Participant.subject_id == subject_id
        )
    )

    if participant is None:
        return None

    session = db.scalar(
        select(QuestionnaireSession).where(
            QuestionnaireSession.participant_id == participant.id,
            QuestionnaireSession.questionnaire_id == questionnaire.id,
        )
    )

    return session

'''
question variant query
'''
def find_question_variant(
    db,
    questionnaire_id: int,
    question_number: str,
    gender_form: str | None,
):
    query = select(
        QuestionVariant
    ).where(
        QuestionVariant.questionnaire_id
        == questionnaire_id,

        QuestionVariant.question_number
        == question_number,
    )

    if gender_form is not None:
        query = query.where(
            QuestionVariant.gender_form
            == gender_form
        )

    return db.scalar(query)


'''
store one response
'''
def add_response(db,session_id: int, question_variant_id: int,value,):
    if pd.isna(value):
        return False

    existing = db.scalar(
        select(Response).where(
            Response.session_id == session_id,
            Response.question_variant_id == question_variant_id,
        )
    )

    if existing is not None:
        return False

    try:
        value_numeric = float(value)
        value_text = None
    except (TypeError, ValueError):
        value_numeric = None
        value_text = str(value)

    response = Response(
        session_id=session_id,
        question_variant_id=question_variant_id,
        value_numeric=value_numeric,
        value_text=value_text,
    )

    db.add(response)
    db.flush()

    return True


'''
main function
'''
def import_responses(db, df: pd.DataFrame, questionnaire_code: str, subject_id_column: str = "subject id", ):
    questionnaire = db.scalar(
        select(Questionnaire).where(
            Questionnaire.code == questionnaire_code
        )
    )

    if questionnaire is None:
        raise ValueError(
            f"Questionnaire not found: {questionnaire_code}"
        )

    # Questionnaire 1 may contain several gender-related columns.
    # Questionnaire 2 may contain none.
    gender_columns = get_gender_question_numbers(db=db,questionnaire_id=questionnaire.id,)

    inserted = 0
    skipped = 0
    missing_question = 0
    missing_session = 0

    # ----------------------------------------
    # Loop over participants
    # ----------------------------------------
    for _, row in df.iterrows():

        subject_id = row.get(subject_id_column)

        if pd.isna(subject_id):
            skipped += 1
            continue

        subject_id = int(subject_id)

        # Find this participant's questionnaire session
        session = get_session(db=db,subject_id=subject_id, questionnaire_code=questionnaire_code,)

        if session is None:
            missing_session += 1
            continue

        # Determine male/female form if relevant
        gender_form = get_gender_form(
            row=row,
            gender_columns=gender_columns,
        )

        # ----------------------------------------
        # Loop over questionnaire answers
        # ----------------------------------------
        for column in df.columns:

            question_number = extract_question_number(column)

            if question_number is None:
                continue

            variant = find_question_variant(db=db, questionnaire_id=questionnaire.id, question_number=question_number,
                                            gender_form=gender_form,)

            if variant is None:
                missing_question += 1
                continue

            value = row[column]

            if pd.isna(value):
                continue

            created = add_response(db=db,session_id=session.id, question_variant_id=variant.id, value=value,)

            if created:
                inserted += 1

    db.commit()

    return {
        "inserted": inserted,
        "skipped": skipped,
        "missing_session": missing_session,
        "missing_question": missing_question,
    }
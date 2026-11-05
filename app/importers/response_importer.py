
import re
from collections import Counter, defaultdict

import pandas as pd
from sqlalchemy import select

from app.database.models import (
    Participant,
    Questionnaire,
    QuestionnaireSession,
    CanonicalQuestion,
    QuestionVariant,
    Response,
)


# ============================================================
# 1. EXTRACT QUESTION NUMBER
# ============================================================

def extract_question_number(column_name):
    """
    Examples:
        Q12        -> Q12
        q12.1      -> Q12.1
        Q5.other   -> Q5.other
        Q13.detail -> Q13.detail
    """

    if not isinstance(column_name, str):
        return None

    value = column_name.strip()

    match = re.fullmatch(
        r"Q\d+(?:\.\d+|\.(?:other|detail))?",
        value,
        flags=re.IGNORECASE,
    )

    if match:
        return "Q" + value[1:]

    return None


# ============================================================
# 2. FIND QUESTIONNAIRE SESSION
# ============================================================

def get_session(db, subject_id, questionnaire_code):

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

    return db.scalar(
        select(QuestionnaireSession).where(
            QuestionnaireSession.participant_id == participant.id,
            QuestionnaireSession.questionnaire_id == questionnaire.id,
        )
    )


# ============================================================
# 3. LOAD QUESTION VARIANTS AND CANONICAL QUESTIONS
# ============================================================

def load_question_mapping(db, questionnaire_id):
    """
    Load variants together with their canonical questions.

    Mapping:
        question_number -> list of (variant, canonical)

    The canonical question must belong to the same
    questionnaire as the variant.
    """

    rows = db.execute(
        select(QuestionVariant, CanonicalQuestion)
        .join(
            CanonicalQuestion,
            QuestionVariant.canonical_question_id
            == CanonicalQuestion.id,
        )
        .where(
            QuestionVariant.questionnaire_id
            == questionnaire_id
        )
    ).all()

    mapping = defaultdict(list)

    for variant, canonical in rows:

        if canonical.questionnaire_id != questionnaire_id:
            raise ValueError(
                "Canonical questionnaire mismatch: "
                f"variant_id={variant.id}, "
                f"canonical_id={canonical.id}"
            )

        number = extract_question_number(
            variant.question_number
        )

        if number is None:
            raise ValueError(
                "Invalid database question number: "
                f"{variant.question_number}"
            )

        mapping[number].append(
            (variant, canonical)
        )

    return mapping


# ============================================================
# 4. ADD ONE RESPONSE
# ============================================================

def add_response(
    db,
    session_id,
    question_variant_id,
    value,
):

    if pd.isna(value):
        return False

    existing = db.scalar(
        select(Response).where(
            Response.session_id == session_id,
            Response.question_variant_id == question_variant_id,
        )
    )

    # Never overwrite an existing response
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


# ============================================================
# 5. PRINT DIAGNOSTIC REPORT
# ============================================================

def print_mapping_report(
    questionnaire_code,
    missing_variants,
    opposite_gender,
    ambiguous_variants,
    duplicate_canonical,
):

    print("\n" + "=" * 70)
    print("QUESTION MAPPING REPORT")
    print("=" * 70)

    print("Questionnaire:", questionnaire_code)

    print(
        "Opposite-gender answers skipped:",
        sum(opposite_gender.values())
    )

    print(
        "Missing question occurrences:",
        sum(missing_variants.values())
    )

    print(
        "Ambiguous mapping occurrences:",
        sum(ambiguous_variants.values())
    )

    print(
        "Duplicate canonical occurrences:",
        sum(duplicate_canonical.values())
    )

    for title, counter in [
        ("MISSING QUESTIONS", missing_variants),
        ("AMBIGUOUS VARIANTS", ambiguous_variants),
        ("DUPLICATE CANONICAL QUESTIONS", duplicate_canonical),
    ]:

        if not counter:
            continue

        print("\n" + title)
        print("-" * 70)

        for key, count in sorted(counter.items()):
            print(f"{key}: {count}")

    print("=" * 70)


# ============================================================
# 6. IMPORT RESPONSES
# ============================================================

def import_responses(
    db,
    df: pd.DataFrame,
    questionnaire_code: str,
    created_session_ids,
    subject_id_column: str = "subject id",
):

    if created_session_ids is None:
        raise ValueError(
            "created_session_ids must be provided"
        )

    allowed_sessions = set(created_session_ids)

    questionnaire = db.scalar(
        select(Questionnaire).where(
            Questionnaire.code == questionnaire_code
        )
    )

    if questionnaire is None:
        raise ValueError(
            f"Questionnaire not found: {questionnaire_code}"
        )

    if subject_id_column not in df.columns:
        raise ValueError(
            f"Missing column: {subject_id_column}"
        )

    # Load mappings once rather than querying
    # PostgreSQL for every individual answer.
    question_mapping = load_question_mapping(
        db,
        questionnaire.id,
    )

    question_columns = [
        (column, extract_question_number(column))
        for column in df.columns
    ]

    question_columns = [
        (column, number)
        for column, number in question_columns
        if number is not None
        # Questionnaire 2's Q1 collects the subject ID, not a response.
        and not (questionnaire_code == "second-questionnaire" and number == "Q1")
    ]

    inserted = 0
    skipped = 0
    missing_session = 0

    missing_variants = Counter()
    opposite_gender = Counter()
    ambiguous_variants = Counter()
    duplicate_canonical = Counter()

    # --------------------------------------------------------
    # LOOP OVER PARTICIPANTS
    # --------------------------------------------------------

    for _, row in df.iterrows():

        subject_id = row.get(subject_id_column)

        if pd.isna(subject_id):
            skipped += 1
            continue

        subject_id = int(subject_id)

        session = get_session(
            db,
            subject_id,
            questionnaire_code,
        )

        if session is None:
            missing_session += 1
            continue

        # Existing questionnaire sessions are not changed
        if session.id not in allowed_sessions:
            skipped += 1
            continue

        gender_form = session.wording_form

        if gender_form not in ("male", "female"):
            skipped += 1
            continue

        # Track canonical questions for this session
        seen_canonical = set()

        # ----------------------------------------------------
        # LOOP OVER ANSWERS
        # ----------------------------------------------------

        for column, question_number in question_columns:
            
            value = row[column]

            if pd.isna(value):
                continue

            candidates = question_mapping.get(
                question_number,
                [],
            )

            # Question number absent from metadata
            if not candidates:
                missing_variants[
                    (question_number, gender_form)
                ] += 1
                continue

            # Find variants for participant's wording
            matching = [
                (variant, canonical)
                for variant, canonical in candidates
                if variant.gender_form == gender_form
            ]
            
            # Q1 in Questionnaire 1 is shared by both genders.
            # Use its existing variant regardless of wording_form.
            if (
                questionnaire_code == "first-questionnaire"
                and question_number == "Q1"
                and not matching
            ):
                matching = [
                    (variant, canonical)
                    for variant, canonical in candidates
                    if canonical.code == "DEMOG_HEALTH_01"
                ]
            
            

            # Known question belonging to opposite gender
            if not matching:
                opposite_gender[
                    (question_number, gender_form)
                ] += 1
                continue

            # Do not guess between multiple mappings
            if len(matching) != 1:
                ambiguous_variants[
                    (question_number, gender_form)
                ] += 1
                continue

            variant, canonical = matching[0]

            if canonical.id in seen_canonical:
                duplicate_canonical[
                    (canonical.code, gender_form)
                ] += 1
                continue

            seen_canonical.add(canonical.id)

            created = add_response(
                db=db,
                session_id=session.id,
                question_variant_id=variant.id,
                value=value,
            )

            if created:
                inserted += 1

    # --------------------------------------------------------
    # DIAGNOSTIC REPORT
    # --------------------------------------------------------

    print_mapping_report(
        questionnaire_code,
        missing_variants,
        opposite_gender,
        ambiguous_variants,
        duplicate_canonical,
    )

    missing_question = sum(missing_variants.values())
    ambiguous_count = sum(ambiguous_variants.values())
    duplicate_count = sum(duplicate_canonical.values())

    print("\nRESPONSE IMPORT SUMMARY")
    print("-" * 45)
    print("Questionnaire:", questionnaire_code)
    print("Inserted responses:", inserted)
    print("Skipped rows:", skipped)
    print("Missing sessions:", missing_session)
    print("Missing questions:", missing_question)
    print("Ambiguous mappings:", ambiguous_count)
    print("Duplicate canonical mappings:", duplicate_count)

    # No db.commit() here.
    # The main script controls the transaction.

    return {
        "inserted": inserted,
        "skipped": skipped,
        "missing_session": missing_session,
        "missing_question": missing_question,
        "ambiguous_variants": ambiguous_count,
        "duplicate_canonical": duplicate_count,
        "opposite_gender_skipped": sum(
            opposite_gender.values()
        ),
        "missing_variants": dict(missing_variants),
    }



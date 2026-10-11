import re
from difflib import SequenceMatcher

import pandas as pd


OK_THRESHOLD = 0.80
REVIEW_THRESHOLD = 0.55


def clean_test_psicolog_name(name: str) -> str:
    name = str(name).upper()
    name = re.sub(r"\d+", "", name)
    name = re.sub(r"[^A-Zא-ת]+", "_", name)

    return name.strip("_")


def normalize_question_text(text) -> str:
    if not isinstance(text, str):
        return ""

    text = text.strip()

    # Remove Q number
    text = re.sub(
        r"^Q\d+(?:\.\d+)?[\s.:\-]*",
        "",
        text,
    )

    # Remove punctuation
    text = re.sub(
        r'[.,;:!?()"״׳]',
        " ",
        text,
    )

    # Normalize spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def text_similarity(text1, text2) -> float:
    text1 = normalize_question_text(text1)
    text2 = normalize_question_text(text2)

    if not text1 or not text2:
        return 0.0

    return SequenceMatcher(None, text1, text2,).ratio()


def clean_text_value(value) -> str:
    if pd.isna(value):
        return ""

    return str(value).strip()


def get_row_question_text(row) -> str:
    parts = []

    question = clean_text_value(
        row.get("question")
    )
    subquestion = clean_text_value(
        row.get("subquestion")
    )

    if not subquestion:
        subquestion = clean_text_value(
            row.get("subquestion phrase")
        )

    if question:
        parts.append(question)

    if subquestion and subquestion.lower() != "answer":
        parts.append(subquestion)

    return " ".join(parts)


def find_best_gender_pairs(men, women):
    candidates = []

    for male_position, male in men.iterrows():
        male_text = get_row_question_text(male)

        for female_position, female in women.iterrows():
            female_text = get_row_question_text(female)
            similarity = text_similarity(
                male_text,
                female_text,
            )

            candidates.append(
                (
                    similarity,
                    male_position,
                    female_position,
                )
            )

    candidates.sort(
        reverse=True,
        key=lambda item: item[0],
    )

    matched_men = set()
    matched_women = set()
    pairs_by_male = {}
    pairs_by_female = {}

    for similarity, male_position, female_position in candidates:
        if similarity < REVIEW_THRESHOLD:
            continue

        if male_position in matched_men:
            continue

        if female_position in matched_women:
            continue

        matched_men.add(male_position)
        matched_women.add(female_position)

        pairs_by_male[male_position] = (
            female_position,
            similarity,
        )
        pairs_by_female[female_position] = (
            male_position,
            similarity,
        )

    return pairs_by_male, pairs_by_female


def get_pair_status(male_text, female_text,threshold=OK_THRESHOLD,):
    if not male_text or not female_text:
        return "MISSING", 0.0

    similarity = text_similarity(male_text,female_text,)

    if similarity >= threshold:
        status = "OK"
    else:
        status = "REVIEW"

    return status, similarity


def assign_canonical_questions(df: pd.DataFrame,) -> pd.DataFrame:

    df = df.copy()

    df["item_order"] = pd.NA
    df["canonical_question"] = None
    df["pair_similarity"] = pd.NA
    df["pair_status"] = None

    groups = df.groupby(["file name", "questionnaire"],sort=False,)

    for (file_name, questionnaire,), group in groups:

        test_psicolog = clean_test_psicolog_name(file_name)

        men = (group[group["gender_form"] == "male"].reset_index())

        women = (group[group["gender_form"] == "female"].reset_index())

        pairs_by_male, pairs_by_female = find_best_gender_pairs(
            men,
            women,
        )

        next_item_order = 1

        for male_position, male in men.iterrows():

            item_order = next_item_order
            next_item_order += 1
            canonical_code = f"{test_psicolog}_{item_order:02d}"
            female_pair = pairs_by_male.get(male_position)

            if female_pair is None:
                status = "MISSING"
                similarity = 0.0
            else:
                _, similarity = female_pair

                if similarity >= OK_THRESHOLD:
                    status = "OK"
                else:
                    status = "REVIEW"

            male_index = male["index"]
            df.loc[male_index, "item_order"] = item_order
            df.loc[male_index, "canonical_question"] = canonical_code
            df.loc[male_index, "pair_similarity"] = similarity
            df.loc[male_index, "pair_status"] = status

            if female_pair is not None:
                female_position, _ = female_pair
                female = women.loc[female_position]
                female_index = female["index"]

                df.loc[female_index, "item_order"] = item_order
                df.loc[female_index, "canonical_question"] = canonical_code
                df.loc[female_index, "pair_similarity"] = similarity
                df.loc[female_index, "pair_status"] = status

        for female_position, female in women.iterrows():
            if female_position in pairs_by_female:
                continue

            item_order = next_item_order
            next_item_order += 1
            canonical_code = f"{test_psicolog}_{item_order:02d}"
            female_index = female["index"]

            df.loc[female_index, "item_order"] = item_order
            df.loc[female_index, "canonical_question"] = canonical_code
            df.loc[female_index, "pair_similarity"] = 0.0
            df.loc[female_index, "pair_status"] = "MISSING"

    df["item_order"] = (pd.to_numeric(df["item_order"],errors="coerce",).astype("Int64"))

    df["pair_similarity"] = pd.to_numeric(df["pair_similarity"],errors="coerce",)

    return df

import re
from difflib import SequenceMatcher

import pandas as pd


OK_THRESHOLD = 0.80


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

        number_items = max(len(men),len(women),)

        for i in range(number_items):

            item_order = i + 1

            male = (men.iloc[i] if i < len(men) else None)

            female = (women.iloc[i] if i < len(women) else None)

            male_text = (male["question"] if male is not None else None)

            female_text = (female["question"] if female is not None else None)

            status, similarity = get_pair_status(male_text,female_text,)

            canonical_code = (f"{test_psicolog}_{item_order:02d}")

            # Male row
            if male is not None:
                index = male["index"]

                df.loc[index, "item_order"] = item_order
                df.loc[index, "canonical_question"] = canonical_code
                df.loc[index, "pair_similarity"] = similarity
                df.loc[index, "pair_status"] = status

            # Female row
            if female is not None:
                index = female["index"]
                df.loc[index, "item_order"] = item_order
                df.loc[index, "canonical_question"] = canonical_code
                df.loc[index, "pair_similarity"] = similarity
                df.loc[index, "pair_status"] = status

    df["item_order"] = (pd.to_numeric(df["item_order"],errors="coerce",).astype("Int64"))

    df["pair_similarity"] = pd.to_numeric(df["pair_similarity"],errors="coerce",)

    return df

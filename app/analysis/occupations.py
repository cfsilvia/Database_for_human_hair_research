from difflib import SequenceMatcher
from functools import lru_cache
import re

from sqlalchemy import select

from app.database.models import Occupation, OccupationOverride


SECOND_GROUP_BY_ANSWER = {
    "סטודנט": "Y24",
    "סטודנטית": "Y24",
}


def occupation_key(answer):
    return " ".join(re.findall(r"[^\W_]+", str(answer or "").casefold()))


@lru_cache(maxsize=2048)
def occupation_words(answer):
    ignored = {"של", "עם", "את", "אני", "בתור", "בתחום", "עובד", "עובדת", "עובדים"}
    words = set()
    for word in occupation_key(answer).split():
        if len(word) < 3 or word in ignored:
            continue
        for suffix in ("יות", "ים", "ות", "ית", "ת"):
            minimum = 4 if suffix == "ת" else 3
            if word.endswith(suffix) and len(word) - len(suffix) >= minimum:
                word = word[:-len(suffix)]
                break
        words.add(word)
    return frozenset(words)


@lru_cache(maxsize=8192)
def occupation_word_similarity(word, target):
    if word == target:
        return 1.0
    if min(len(word), len(target)) < 4:
        return 0.0
    return SequenceMatcher(None, word, target).ratio()


def find_occupation_matches(answer, by_name):
    key = occupation_key(answer)
    if key in by_name:
        return by_name[key]

    # Extra student details may describe a study subject rather than a profession.
    if any(word in SECOND_GROUP_BY_ANSWER for word in key.split()):
        return set()

    words = occupation_words(answer)
    candidates = []
    for name, values in by_name.items():
        name_words = occupation_words(name)
        similarities = []
        for word in words:
            similarity = max((
                occupation_word_similarity(word, target)
                for target in name_words
            ), default=0.0)
            if similarity >= 0.80:
                similarities.append(similarity)
        if similarities:
            candidates.append((len(similarities), sum(similarities), values))

    if not candidates:
        return set()

    best_count, best_score = max((count, score) for count, score, _ in candidates)
    return {
        value for count, score, values in candidates
        if count == best_count and best_score - score <= 0.05 + 1e-12
        for value in values
    }


def get_occupation_columns():
    return {
        "test": "Occupation",
        "columns": [
            {"key": "occupation_major", "label": "Major group"},
            {"key": "occupation_first_group", "label": "First group"},
            {"key": "occupation_second_group", "label": "Second group"},
            {"key": "occupation_source", "label": "Classification source"},
            {"key": "occupation_review", "label": "Occupation review"},
        ],
    }


def get_occupation_values(db, occupation_answers):
    fields = (
        "major_code",
        "major_group_he",
        "first_group_code",
        "first_group_he",
        "second_group_code",
        "second_group_he",
    )
    by_name = {}
    by_second_code = {}

    for occupation in db.scalars(select(Occupation)):
        values = tuple(getattr(occupation, field) for field in fields)
        name = occupation_key(occupation.occupation_he)
        by_name.setdefault(name, set()).add(values)
        by_second_code.setdefault(occupation.second_group_code, set()).add(values)

    results = {}

    for subject_id, answer in occupation_answers.items():
        key = occupation_key(answer)
        second_code = SECOND_GROUP_BY_ANSWER.get(key)

        if second_code is not None:
            matches = by_second_code.get(second_code, set())
        else:
            matches = find_occupation_matches(answer, by_name) if key else set()

        result = dict.fromkeys(fields, "Unknown")
        for index in (0, 2, 4):
            pairs = {(values[index], values[index + 1]) for values in matches}
            if len(pairs) != 1:
                break
            result[fields[index]], result[fields[index + 1]] = next(iter(pairs))
        results[subject_id] = result

    return results


def normalize_occupation_answer(answer):
    return " ".join(str(answer or "").casefold().split())


def occupation_answers_match(current_answer, saved_answer):
    return bool(normalize_occupation_answer(current_answer)) and (
        normalize_occupation_answer(current_answer) == normalize_occupation_answer(saved_answer)
    )


def occupation_labels_equal(automatic_label, ai_label):
    unknown = {"", "unknown", "לא ניתן לקבוע", "בעלי משלח יד לא ידוע"}

    def labels(value):
        normalized = {" ".join(line.split()).casefold() for line in str(value or "").splitlines()}
        normalized.discard("")
        return {"Unknown" if label in unknown else label for label in normalized} or {"Unknown"}

    return labels(automatic_label) == labels(ai_label)


def build_occupation_review(automatic, ai, saved_review):
    differences = [
        f"{key}: {automatic[key]['label']} → {ai[key]['label']}"
        for key in automatic
        if not occupation_labels_equal(automatic[key]["label"], ai[key]["label"])
    ]
    comparison = "Automatic → AI:\n" + "\n".join(differences) if differences else ""
    return "\n\n".join(text for text in (saved_review, comparison) if text)


def add_occupation_values(db, rows, questions, answer_labels):
    question_keys = {
        f"canonical_{question.canonical_id}"
        for question in questions
        if occupation_key(question.question).strip("?؟ ") == "מהו העיסוק שלך"
    }
    occupation_answers = {}

    for row in rows:
        answers = {
            normalize_occupation_answer(row.get(key))
            for key in question_keys
            if occupation_key(row.get(key))
        }
        occupation_answers[row["subject_id"]] = (
            next(iter(answers)) if len(answers) == 1 else None
        )

    occupations = get_occupation_values(db, occupation_answers)
    overrides = {
        item.subject_id: item for item in db.scalars(
            select(OccupationOverride).where(OccupationOverride.subject_id.in_(occupation_answers))
        )
    }
    comparisons = {}
    fields = (
        ("major", "major_group_he"),
        ("first_group", "first_group_he"),
        ("second_group", "second_group_he"),
    )

    for row in rows:
        subject_id = row["subject_id"]
        occupation = occupations[subject_id]
        override = overrides.get(subject_id)
        use_ai = override is not None and occupation_answers_match(
            occupation_answers[subject_id], override.occupation_answer,
        )
        automatic = {
            f"occupation_{field}": {
                "code": occupation[f"{field}_code"], "label": occupation[label_field],
            }
            for field, label_field in fields
        }
        row["occupation_source"] = "AI" if use_ai else "Automatic"
        row["occupation_review"] = ""
        if use_ai:
            ai = {
                f"occupation_{field}": {
                    "code": getattr(override, f"{field}_code"),
                    "label": getattr(override, label_field),
                }
                for field, label_field in fields
            }
            comparisons[str(subject_id)] = {
                "automatic": automatic,
                "different_columns": [
                    key for key in automatic
                    if not occupation_labels_equal(automatic[key]["label"], ai[key]["label"])
                ],
            }
            row["occupation_review"] = build_occupation_review(automatic, ai, override.review)
        elif override is not None:
            row["occupation_review"] = (
                "Occupation answer changed, missing, or conflicting; AI review needs updating."
            )

        for field, label_field in fields:
            key = f"occupation_{field}"
            row[key] = getattr(override, f"{field}_code") if use_ai else occupation[f"{field}_code"]
            if row[key] != "Unknown":
                answer_labels.setdefault(str(subject_id), {})[key] = (
                    getattr(override, label_field) if use_ai else occupation[label_field]
                )
    return comparisons

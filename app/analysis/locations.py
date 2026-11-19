from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
import re

from openpyxl import load_workbook
from sqlalchemy import select

from app.database.models import Locality


def locality_key(name):
    return " ".join(re.sub(r"[^\w\s]", " ", str(name or "").casefold()).split())


@lru_cache(maxsize=1)
def read_english_locality_names():
    path = Path(__file__).resolve().parents[2] / "data/incoming/location.xlsx"
    if not path.exists():
        return {}
    workbook = load_workbook(path, read_only=True, data_only=True)
    names = {}
    try:
        rows = workbook["Location_register"].iter_rows(values_only=True)
        headers = next(rows)
        hebrew_index = headers.index("locality_he")
        english_index = headers.index("locality_latin")
        for row in rows:
            if row[english_index] and row[hebrew_index]:
                names.setdefault(locality_key(row[english_index]), set()).add(row[hebrew_index])
    finally:
        workbook.close()
    return names


def is_overseas(answer):
    name = locality_key(re.sub(r"\([^)]*\)", "", answer))
    return name in {
        "חול", "בחול", "חו ל", "בחו ל", "abroad",
        "גואה", "goa", "ונציה", "venice",
    }


def find_locality(answer, by_name, normalized, english_names):
    if answer in by_name:
        return {answer}, False
    if is_overseas(answer):
        return set(), False
    key = locality_key(answer)
    # Do not interpret multiple places as a single approximate match.
    if re.search(r"[/;\n,]|\sו\S+", answer):
        return set(), False
    if key in normalized:
        return normalized[key], False
    aliases = {
        "מודיעין": "מודיעין מכבים רעות",
        "פרדס חנה": "פרדס חנה כרכור",
        "תל אביב": "תל אביב יפו",
        "יפו": "תל אביב יפו",
        "הרצליה": "הרצלייה",
        "kiryat ono": "קריית אונו",
        "qiryat ono": "קריית אונו",
    }
    target = aliases.get(key, re.sub(r"^(קיבוץ|מושב)\s+", "", key))
    if target in normalized:
        return normalized[target], False
    if key in english_names:
        return english_names[key], False
    if len(key.replace(" ", "")) < 4:
        return set(), False
    search_names = english_names | normalized
    candidates = sorted(
        ((SequenceMatcher(None, key, name).ratio(), name) for name in search_names),
        reverse=True,
    )
    if not candidates or candidates[0][0] < 0.80:
        return set(), False
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 0.10 - 1e-12:
        return set(), False
    return search_names[candidates[0][1]], True


def get_location_values(db, locality_answers):
    """Resolve locality answers without changing stored questionnaire responses."""
    by_name = {}
    normalized = {}
    for locality in db.scalars(select(Locality)):
        values = (
            locality.district_code, locality.district_he,
            locality.subdistrict_code, locality.subdistrict_he,
        )
        name = locality.locality_he.strip()
        by_name.setdefault(name, set()).add(values)
        normalized.setdefault(locality_key(name), set()).add(name)

    english_names = {}
    for english_name, hebrew_names in read_english_locality_names().items():
        names = {name for hebrew_name in hebrew_names
                 for name in normalized.get(locality_key(hebrew_name), set())}
        if names:
            english_names[english_name] = names
    results = {}
    for subject_id, answer in locality_answers.items():
        answer = str(answer or "").strip()
        names, approximate = find_locality(answer, by_name, normalized, english_names)
        matches = {value for name in names for value in by_name[name]}
        # Duplicate names are usable only when all matches share the same codes.
        pairs = {(value[0], value[2]) for value in matches}
        # Missing or ambiguous localities receive Unknown for all four fields.
        values = next(iter(matches)) if len(pairs) == 1 else ("Unknown",) * 4
        if not matches and is_overseas(answer):
            values = (0, 'חו"ל', 0, 'חו"ל')
        results[subject_id] = dict(zip(
            ("district_code", "district_he", "subdistrict_code", "subdistrict_he"),
            values,
        ))
        if approximate and len(pairs) == 1:
            results[subject_id].update(is_approximate=True, matched_locality=sorted(names)[0])

    return results

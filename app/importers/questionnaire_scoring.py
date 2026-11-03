"""Read and import response labels, scoring rules, and their question links."""

from pathlib import Path
import re
import sys

# Allow this file to run directly with the IDE's Run/Debug Python File button.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from openpyxl import load_workbook
from sqlalchemy import select

from app.database.models import (
    CanonicalQuestion, Questionnaire, QuestionVariant, ResponseValueLabel,
    QuestionnaireScoringRule, ScoringRuleQuestion,
)


DEFAULT_WORKBOOK = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "incoming"
    / "Quest and scoring_to_use.xlsx"
)

def read_response_label(header):
    """Remove the numeric suffix, keeping the original Hebrew response text."""
    match = re.fullmatch(r"(.+?)\s*\(-?\d+(?:/-?\d+)*\)\s*", str(header), flags=re.DOTALL)

    if match is None:
        raise ValueError(f"Invalid response heading: {header!r}")

    return match.group(1)


def read_questionnaire_sheet(sheet_name, file_path):
    """Read named columns and any number of integer-scored answer options."""
    workbook = load_workbook(file_path, read_only=True, data_only=True)
    try:
        sheet = workbook[sheet_name]
        headers = list(next(sheet.iter_rows(values_only=True)))
        required = ("questionnaire_code", "item_number", "question_text")
        if not all(name in headers for name in required):
            raise ValueError(f"{sheet_name}: missing question columns")
        options = [
            (i, read_response_label(header))
            for i, header in enumerate(headers)
            if re.fullmatch(r".+?\s*\(-?\d+(?:/-?\d+)*\)\s*", str(header), flags=re.DOTALL)
        ]
        allowed = {
            int(score)
            for i, _ in options
            for score in re.search(r"\((-?\d+(?:/-?\d+)*)\)\s*$", str(headers[i])).group(1).split("/")
        }
        if not options or (sheet_name != "AQ" and len(allowed) != len(options)):
            raise ValueError(f"{sheet_name}: missing or duplicate answer scores")
        supported = {*required, "subscale_name", "test_name", *(headers[i] for i, _ in options)}
        unknown = [header for header in headers if header is not None and header not in supported]
        if unknown:
            raise ValueError(f"{sheet_name}: unsupported columns {unknown}; add a database mapping first")
        records = []
        seen = set()
        for row_number, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), 2):
            if all(value is None for value in row):
                continue
            data = dict(zip(headers, row))
            form, number = data["questionnaire_code"], str(data["item_number"]).strip()
            if not isinstance(form, str) and (type(form) not in (int, float) or not float(form).is_integer()):
                raise ValueError(f"{sheet_name} row {row_number}: invalid questionnaire code")
            form = str(int(form)) if type(form) in (int, float) else form.strip()
            if not form:
                raise ValueError(f"{sheet_name} row {row_number}: missing questionnaire code")
            if not number.isdecimal() or int(number) < 1:
                raise ValueError(f"{sheet_name} row {row_number}: invalid item number")
            if not isinstance(data["question_text"], str) or not data["question_text"].strip():
                raise ValueError(f"{sheet_name} row {row_number}: missing question text")
            key = (form, int(number))
            if key in seen:
                raise ValueError(f"{sheet_name} row {row_number}: duplicate item {key}")
            seen.add(key)
            values = [row[i] for i, label in options]
            if (any(type(v) not in (int, float) or v not in allowed for v in values)
                    or (sheet_name != "AQ" and len(set(values)) != len(values))):
                raise ValueError(f"{sheet_name} row {row_number}: invalid scores {values!r}")
            for position, (column, label) in enumerate(options, 1):
                records.append({
                    "source_question_number": int(number),
                    "question_text": data["question_text"], "form_number": form,
                    "test_name": data.get("test_name"),
                    "option_position": position, "numeric_value": int(row[column]),
                    "text_male": label, "text_female": label,
                    "source_sheet": sheet_name, "source_row": row_number,
                    "subscale": data.get("subscale_name"), "description_he": None,
                })
        return records
    finally:
        workbook.close()


def normalize_question_text(value):
    """Ignore punctuation and spacing only when comparing question text."""
    text = re.sub(r"[^\w\s]", " ", value or "")
    return " ".join(text.split())


def find_question_id(db, questionnaire_id, test_name, question_text):
    """Match Hebrew wording to one canonical question; never guess a match."""
    target = normalize_question_text(question_text)
    if not target:
        raise ValueError("Cannot match an empty question")

    candidates = db.execute(
        select(CanonicalQuestion.id, QuestionVariant.question, CanonicalQuestion.test_psicolog)
        .join(QuestionVariant, QuestionVariant.canonical_question_id == CanonicalQuestion.id)
        .where(
            CanonicalQuestion.questionnaire_id == questionnaire_id,
            QuestionVariant.questionnaire_id == questionnaire_id,
        )
    ).all()

    # Male and female variants may both point to the same canonical question.
    matches = set()
    for question_id, wording, candidate_test in candidates:
        if normalize_question_text(wording) == target and (test_name is None or candidate_test == test_name):
            matches.add(question_id)

    if len(matches) != 1:
        raise ValueError(
            f"Expected one Hebrew match for {test_name}, questionnaire "
            f"{questionnaire_id}: {question_text!r}; found IDs {sorted(matches)}"
        )

    return matches.pop()


def match_question_records(db, records):
    """Add existing questionnaire/question IDs without changing database records."""
    form_codes = {"1": "first-questionnaire", "2": "second-questionnaire"}
    questionnaire_ids = {}
    question_ids = {}
    matched = []

    for record in records:
        form = record["form_number"]
        if form not in questionnaire_ids:
            code = form_codes.get(form, form)
            questionnaire_id = db.scalar(
                select(Questionnaire.id).where(Questionnaire.code == code)
            )
            if questionnaire_id is None:
                raise ValueError(f"Missing questionnaire: {code}")
            questionnaire_ids[form] = questionnaire_id

        questionnaire_id = questionnaire_ids[form]
        key = (form, record.get("test_name"), record["question_text"])
        if key not in question_ids:
            wording = record["question_text"]
            question_ids[key] = find_question_id(
                db, questionnaire_id, record.get("test_name"), wording
            )

        matched.append({
            **record,
            "questionnaire_id": questionnaire_id,
            "question_id": question_ids[key],
            "test_name": db.get(CanonicalQuestion, question_ids[key]).test_psicolog,
        })

    # One workbook question must not silently match another workbook question's ID.
    source_by_id = {}
    for record in matched:
        source = (record["form_number"], record.get("source_question_number"))
        previous = source_by_id.setdefault(record["question_id"], source)
        if previous != source:
            raise ValueError(f"Multiple source questions match ID {record['question_id']}")

    if len({r["test_name"] for r in matched}) > 1:
        raise ValueError("A test sheet matched multiple database tests; add an explicit test_name column")
    return matched


def read_and_match_all(db, file_path=DEFAULT_WORKBOOK):
    """Discover test sheets and match their questions without database writes."""
    workbook = load_workbook(file_path, read_only=True, data_only=True)
    try:
        sheets = [name for name in workbook.sheetnames if not name.endswith("_scoring_rules")]
        orphans = [name for name in workbook.sheetnames
                   if name.endswith("_scoring_rules") and name[:-14] not in sheets]
        if orphans:
            raise ValueError(f"Scoring sheets have no question sheet: {orphans}")
    finally:
        workbook.close()
    return {
        sheet: match_question_records(db, read_questionnaire_sheet(sheet, file_path))
        for sheet in sheets
    }


def import_response_labels(db, records, apply=False):
    """Validate labels, skip identical rows, and optionally stage new rows.

    The caller owns the transaction and must commit or roll back.
    Existing rows are never overwritten.
    """
    fields = (
        "question_id", "option_position", "numeric_value", "text_male",
        "text_female", "source_sheet", "source_row",
    )
    question_ids = {record["question_id"] for record in records}
    existing = db.scalars(
        select(ResponseValueLabel).where(ResponseValueLabel.question_id.in_(question_ids))
    ).all()
    by_position = {(row.question_id, row.option_position): row for row in existing}
    pending = []
    seen_positions = set()
    skipped = 0

    for record in records:
        data = {field: record[field] for field in fields}
        position_key = (data["question_id"], data["option_position"])
        if position_key in seen_positions:
            raise ValueError(f"Duplicate input mapping for question {data['question_id']}")
        seen_positions.add(position_key)

        previous = by_position.get(position_key)
        if previous is not None:
            if any(getattr(previous, field) != value for field, value in data.items()
                   if field not in ("source_sheet", "source_row")):
                raise ValueError(
                    f"{data['source_sheet']} item {record['source_question_number']} "
                    f"(Excel row {data['source_row']}): existing label conflicts "
                    f"with Excel for question/position {position_key}"
                )
            skipped += 1
        else:
            pending.append(ResponseValueLabel(**data))

    if apply:
        db.add_all(pending)

    return {"new": len(pending), "existing": skipped}


def read_scoring_rules(records_by_sheet, file_path=DEFAULT_WORKBOOK):
    """Read rule sheets and resolve their item membership without database writes."""
    workbook = load_workbook(file_path, read_only=True, data_only=True)
    records = []
    try:
        for sheet_name, items in records_by_sheet.items():
            rule_sheet = f"{sheet_name}_scoring_rules"
            if rule_sheet not in workbook.sheetnames:
                continue
            sheet = workbook[rule_sheet]
            test_names = {item["test_name"] for item in items}
            test_name = next(iter(test_names), None)
            rows = sheet.iter_rows(values_only=True)
            headers = next(rows)
            required = ("test_name", "rule_code", "rule_type", "scoring_method",
                        "subscale_name", "min_score", "max_score", "range_min",
                        "range_max", "interpretation_he", "parent_rule_code")
            if not all(field in headers for field in required):
                raise ValueError(f"{sheet.title}: missing rule columns")
            optional = ("description_he", "notes", "is_enabled")
            unknown = [header for header in headers if header is not None and header not in (*required, *optional)]
            if unknown:
                raise ValueError(f"{sheet.title}: unsupported columns {unknown}; add a database mapping first")
            questions = {
                row["question_id"]: row for row in records_by_sheet[sheet_name]
            }
            sheet_rules = []
            for row_number, row in enumerate(rows, 2):
                if all(value is None for value in row):
                    continue
                data = dict(zip(headers, row))
                if (data["test_name"] not in (sheet_name, test_name)
                        or not isinstance(data["rule_code"], str) or not data["rule_code"].strip()):
                    raise ValueError(f"{sheet.title} row {row_number}: invalid test or rule code")
                enabled = data.get("is_enabled")
                if enabled is None:
                    enabled = True
                if type(enabled) is not bool:
                    raise ValueError(f"{sheet.title} row {row_number}: is_enabled must be TRUE or FALSE")
                kind = data["rule_type"]
                if kind not in ("total", "subscale", "interpretation"):
                    raise ValueError(f"{sheet.title} row {row_number}: invalid rule type")
                members = {}
                if kind != "interpretation":
                    if data["scoring_method"] != "sum" or data["parent_rule_code"] is not None:
                        raise ValueError(f"{sheet.title} row {row_number}: invalid sum rule")
                    if kind == "subscale" and not data["subscale_name"]:
                        raise ValueError(f"{sheet.title} row {row_number}: missing subscale")
                    members = {
                        question_id: item["source_question_number"]
                        for question_id, item in questions.items()
                        if kind == "total" or item["subscale"] == data["subscale_name"]
                    }
                    if not members:
                        raise ValueError(f"{sheet.title} row {row_number}: no matching questions")
                    scores = records_by_sheet[sheet_name]
                    limits = [
                        sum(function(r["numeric_value"] for r in scores if r["question_id"] == q)
                            for q in members)
                        for function in (min, max)
                    ]
                    if limits != [data["min_score"], data["max_score"]]:
                        raise ValueError(f"{sheet.title} row {row_number}: score limits disagree with items")
                else:
                    low, high = data["range_min"], data["range_max"]
                    if (not data["parent_rule_code"] or not data["interpretation_he"]
                            or data["scoring_method"] is not None
                            or type(low) not in (int, float) or type(high) not in (int, float)
                            or low > high):
                        raise ValueError(f"{sheet.title} row {row_number}: invalid interpretation")
                sheet_rules.append({
                    **{field: data[field] for field in required if field != "parent_rule_code"},
                    "test_name": test_name, "source_sheet": sheet.title,
                    "description_he": data.get("description_he"),
                    "notes": data.get("notes"), "is_enabled": enabled,
                    "parent_rule_code": data["parent_rule_code"], "questions": members,
                })
            if sheet_rules:
                subscales = {r["subscale_name"] for r in sheet_rules if r["rule_type"] == "subscale"}
                if any(q["subscale"] and q["subscale"] not in subscales for q in questions.values()):
                    raise ValueError(f"{sheet.title}: an item subscale has no rule")
            records.extend(sheet_rules)
    finally:
        workbook.close()
    by_key = {(r["test_name"], r["rule_code"]): r for r in records}
    if len(by_key) != len(records):
        raise ValueError("Duplicate scoring rule codes")
    for rule in records:
        if rule["rule_type"] == "interpretation":
            parent = by_key.get((rule["test_name"], rule["parent_rule_code"]))
            if parent is None or parent["rule_type"] not in ("total", "subscale"):
                raise ValueError(f"Missing scoring parent for {rule['rule_code']}")
            if not parent["min_score"] <= rule["range_min"] <= rule["range_max"] <= parent["max_score"]:
                raise ValueError(f"Interpretation exceeds parent limits: {rule['rule_code']}")
    return records


def import_scoring_rules(db, records, apply=False):
    """Validate and stage rules and question links; the caller owns the transaction."""
    fields = ("test_name", "rule_code", "rule_type", "scoring_method", "subscale_name",
              "min_score", "max_score", "range_min", "range_max", "interpretation_he",
              "source_sheet", "description_he", "notes", "is_enabled")
    existing = db.scalars(select(QuestionnaireScoringRule)).all()
    by_key = {(r.test_name, r.rule_code): r for r in existing}
    by_id = {r.id: (r.test_name, r.rule_code) for r in existing}
    objects, pending, links = {}, [], []
    seen = set()
    existing_links = 0
    for record in records:
        data = {field: record[field] for field in fields}
        key = (record["test_name"], record["rule_code"])
        if key in seen:
            raise ValueError(f"Duplicate scoring rule: {key}")
        seen.add(key)
        previous = by_key.get(key)
        parent_key = (record["test_name"], record["parent_rule_code"]) if record["parent_rule_code"] else None
        if previous is not None:
            if (any(getattr(previous, field) != value for field, value in data.items())
                    or by_id.get(previous.parent_rule_id) != parent_key):
                raise ValueError(f"Existing scoring rule conflicts with Excel: {key}")
            objects[key] = previous
            old_links = {r.question_id: r.source_question_number for r in db.scalars(
                select(ScoringRuleQuestion).where(ScoringRuleQuestion.rule_id == previous.id)
            )}
        else:
            objects[key] = QuestionnaireScoringRule(**data)
            pending.append(objects[key])
            old_links = {}
        if any(record["questions"].get(q) != number for q, number in old_links.items()):
            raise ValueError(f"Existing question links conflict with Excel: {key}")
        existing_links += len(old_links)
        links.extend((key, q, number) for q, number in record["questions"].items() if q not in old_links)
    for record in records:
        if record["parent_rule_code"] and (record["test_name"], record["parent_rule_code"]) not in objects:
            raise ValueError(f"Missing scoring parent for {record['rule_code']}")
    if apply:
        db.add_all(pending)
        db.flush()
        for record in records:
            key = (record["test_name"], record["rule_code"])
            if record["parent_rule_code"]:
                objects[key].parent_rule_id = objects[(record["test_name"], record["parent_rule_code"])].id
        db.add_all([
            ScoringRuleQuestion(rule_id=objects[key].id, question_id=q, source_question_number=number)
            for key, q, number in links
        ])
    return {
        "questionnaire_scoring_rules": {"new": len(pending), "existing": len(records) - len(pending)},
        "scoring_rule_questions": {"new": len(links), "existing": existing_links},
    }


def import_scoring_workbook(db, file_path=DEFAULT_WORKBOOK, apply=False):
    """Validate all three tables before staging any changes. Never commit here."""
    matched = read_and_match_all(db, file_path)
    rules = read_scoring_rules(matched, file_path)
    labels = [record for rows in matched.values() for record in rows]
    result = import_scoring_rules(db, rules)
    result["response_value_labels"] = import_response_labels(db, labels)
    if apply:
        import_response_labels(db, labels, apply=True)
        import_scoring_rules(db, rules, apply=True)
    return result

"""Repair the PCL/trauma split; preview by default, save with --apply."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd
from sqlalchemy import select, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.models import (
    CanonicalQuestion, Questionnaire, QuestionVariant, Response,
    ResponseValueLabel, ScoringRuleQuestion,
)
from app.importers.canonical_mapper import assign_canonical_questions
from app.importers.metadata_importer import get_question_fields


def read_items(path, sheets):
    items = {}
    for sheet in sheets:
        df = assign_canonical_questions(pd.read_excel(path, sheet_name=sheet))
        for _, row in df.iterrows():
            fields = get_question_fields(row)
            key = (row["questionnaire"], row["gender_form"], fields["question_number"])
            if key in items:
                raise ValueError(f"Duplicate workbook question: {key}")
            items[key] = dict(row, **fields)
    return items


def affected_records(db):
    questions = db.scalars(select(CanonicalQuestion).where(
        CanonicalQuestion.test_psicolog.in_(("PCL", "trauma-checklist"))
    )).all()
    ids = [q.id for q in questions]
    variants = db.scalars(select(QuestionVariant).where(
        QuestionVariant.canonical_question_id.in_(ids)
    )).all()
    return questions, variants


def repair_metadata(db, workbook, previous_workbook):
    """Stage the repair, retaining original canonical and answered variant IDs."""
    desired = read_items(workbook, ("PCL", "trauma-checklist"))
    previous = read_items(previous_workbook, ("PCL",))
    if desired.keys() != previous.keys():
        raise ValueError("The workbooks must contain the same PCL/trauma question numbers and forms")

    questions, variants = affected_records(db)
    forms = {q.id: q.code for q in db.scalars(select(Questionnaire))}
    by_key = {}
    for variant in variants:
        key = (forms[variant.questionnaire_id], variant.gender_form, variant.question_number)
        by_key.setdefault(key, []).append(variant)
    if by_key.keys() != desired.keys():
        raise ValueError("Database questions differ from the workbooks; no automatic repair is safe")

    by_id = {q.id: q for q in questions}
    if all(
        len(by_key[key]) == 1
        and by_key[key][0].file_name == row["file name"]
        and by_id[by_key[key][0].canonical_question_id].test_psicolog == row["file name"]
        and by_id[by_key[key][0].canonical_question_id].item_order == int(row["item_order"])
        for key, row in desired.items()
    ) and {v.canonical_question_id for v in variants} == set(by_id):
        return {"questions": len(questions), "variants": len(variants), "duplicates_removed": 0,
                "changed": False}

    original = {(forms[q.questionnaire_id], q.item_order): q
                for q in questions if q.test_psicolog == "PCL"}
    expected_original = {(key[0], int(row["item_order"])) for key, row in previous.items()}
    if set(original) != expected_original:
        raise ValueError("Original PCL canonical records do not match the previous workbook")

    updates = {}
    survivors = []
    duplicates = []
    for key, row in desired.items():
        canonical = original[(key[0], int(previous[key]["item_order"]))]
        target = (row["file name"], int(row["item_order"]), row["canonical_question"])
        if canonical.id in updates and updates[canonical.id] != target:
            raise ValueError(f"Male/female pairing changed for {key}")
        updates[canonical.id] = target
        candidates = by_key[key]
        old = [v for v in candidates if v.file_name == "PCL"]
        if len(old) != 1:
            raise ValueError(f"Cannot identify the original answered variant for {key}")
        survivors.append((old[0], canonical.id, row))
        for variant in candidates:
            if variant is old[0]:
                continue
            if variant.file_name != row["file name"] or row["file name"] != "trauma-checklist":
                raise ValueError(f"Unexpected duplicate variant for {key}")
            duplicates.append(variant)

    duplicate_ids = [v.id for v in duplicates]
    if db.scalar(select(Response.id).where(Response.question_variant_id.in_(duplicate_ids)).limit(1)):
        raise ValueError("Duplicate trauma records have answers; refusing to delete them")
    unused = [q for q in questions if q.id not in updates]
    unused_ids = [q.id for q in unused]
    for model in (ResponseValueLabel, ScoringRuleQuestion):
        if db.execute(select(model).where(model.question_id.in_(unused_ids)).limit(1)).first():
            raise ValueError("Duplicate canonical records have scoring links; refusing to delete them")

    for variant in duplicates:
        db.delete(variant)
    db.flush()
    # Release unique (questionnaire, test, order) slots before renumbering.
    for question in questions:
        question.item_order = None
    db.flush()
    for variant, canonical_id, row in survivors:
        variant.canonical_question_id = canonical_id
        variant.file_name = row["file name"]
        for field in ("question", "parent_question_number", "parent_question"):
            setattr(variant, field, row[field])
        variant.pair_status = row["pair_status"]
        variant.pair_similarity = float(row["pair_similarity"])
    db.flush()
    for question in unused:
        db.delete(question)
    db.flush()
    for question_id, (test, order, code) in updates.items():
        question = by_id[question_id]
        question.test_psicolog, question.item_order, question.code = test, order, code
    db.flush()
    return {"questions": len(updates), "variants": len(survivors),
            "duplicates_removed": len(duplicates), "changed": True}


def response_digest(db, variant_ids):
    rows = db.execute(select(Response).where(
        Response.question_variant_id.in_(variant_ids)
    ).order_by(Response.id)).scalars()
    digest = hashlib.sha256()
    count = 0
    for row in rows:
        values = tuple(getattr(row, c.name) for c in Response.__table__.columns)
        digest.update(repr(values).encode("utf-8"))
        count += 1
    return count, digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    from app.database.connection import SessionLocal

    incoming = PROJECT_ROOT / "data" / "incoming"
    with SessionLocal() as db:
        try:
            db.execute(text("SET LOCAL lock_timeout = '10s'"))
            db.execute(text("LOCK TABLE canonical_questions, question_variants, responses, "
                            "response_value_labels, scoring_rule_questions IN SHARE ROW EXCLUSIVE MODE"))
            questions, variants = affected_records(db)
            variant_ids = [v.id for v in variants]
            before = response_digest(db, variant_ids)
            if args.apply:
                backup = {model.__tablename__: [
                    {c.name: getattr(row, c.name) for c in model.__table__.columns}
                    for row in rows
                ] for model, rows in ((CanonicalQuestion, questions), (QuestionVariant, variants))}
                backup["responses_count_and_sha256"] = before
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                path = PROJECT_ROOT / "data" / "metadata_backups" / f"pcl_{stamp}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"Metadata backup: {path}")
            result = repair_metadata(db, incoming / "question_metadata.xlsx",
                                     incoming / "question_metadata_old.xlsx")
            if before != response_digest(db, variant_ids):
                raise ValueError("Response verification failed; rolling back")
            print(result)
            print(f"Verified {before[0]} answers unchanged.")
            if args.apply:
                db.commit()
                print("Repair saved.")
            else:
                db.rollback()
                print("Preview only. Use --apply to save.")
        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()

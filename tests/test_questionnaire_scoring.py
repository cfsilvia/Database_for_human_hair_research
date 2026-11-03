from openpyxl import Workbook, load_workbook
import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.database.models import (
    Base, CanonicalQuestion, Questionnaire, QuestionnaireScoringRule,
    QuestionVariant, ResponseValueLabel, ScoringRuleQuestion,
)
from app.importers.questionnaire_scoring import (
    import_scoring_workbook, read_and_match_all, read_scoring_rules, read_questionnaire_sheet,
)


@pytest.fixture
def scoring_data(tmp_path):
    path = tmp_path / "scoring.xlsx"
    workbook = Workbook()
    workbook.remove(workbook.active)
    layouts = {
        "PSS": ([0, 1, 2, 3, 4], [(1, 1, None), (2, 2, None)]),
        "PHQ4": ([3, 2, 1, 0], [(1, 1, "Depression"), (1, 2, "Anxiety")]),
        "DERS-16": ([1, 2, 3, 4, 5], [(1, 1, "Goals"), (2, 2, "Clarity")]),
        "STAI-T": ([1, 2, 3, 4], [(1, 1, None)]),
    }
    for name, (scores, items) in layouts.items():
        sheet = workbook.create_sheet(name)
        sheet.append(["questionnaire_code", "item_number", "question_text"] +
                     [f"Option {n} ({score})" for n, score in enumerate(scores)] +
                     ["subscale_name"])
        for form, number, subscale in items:
            values = list(reversed(scores)) if name == "PSS" and number == 1 else scores
            sheet.append([form, str(number), f"{name} question {number}", *values, subscale])
    headers = ["test_name", "rule_code", "rule_type", "scoring_method", "subscale_name",
               "min_score", "max_score", "range_min", "range_max", "interpretation_he",
               "parent_rule_code"]
    rules = {
        "PSS": [
            ["low", "interpretation", None, None, None, None, 0, 2, "Low", "total"],
            ["total", "total", "sum", None, 0, 8],
        ],
        "PHQ4": [
            ["total", "total", "sum", None, 0, 6],
            ["depression", "subscale", "sum", "Depression", 0, 3],
            ["anxiety", "subscale", "sum", "Anxiety", 0, 3],
            ["positive", "interpretation", None, "Anxiety", None, None, 3, 3, "Positive", "anxiety"],
        ],
        "DERS-16": [
            ["total", "total", "sum", None, 2, 10],
            ["goals", "subscale", "sum", "Goals", 1, 5],
            ["clarity", "subscale", "sum", "Clarity", 1, 5],
        ],
        "STAI-T": [],
    }
    for name, rows in rules.items():
        sheet = workbook.create_sheet(f"{name}_scoring_rules")
        sheet.append(headers)
        for row in rows:
            sheet.append([name, *row])
    workbook.save(path)
    workbook.close()

    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine, autoflush=False) as db:
        forms = {}
        for form, code in ((1, "first-questionnaire"), (2, "second-questionnaire")):
            questionnaire = Questionnaire(code=code, name=code)
            db.add(questionnaire)
            db.flush()
            forms[form] = questionnaire.id
        for name, (_, items) in layouts.items():
            for form, number, subscale in items:
                question = CanonicalQuestion(
                    questionnaire_id=forms[form], code=f"{name}_{number}",
                    test_psicolog={"PHQ4": "PHQ", "DERS-16": "DERS", "STAI-T": "STAI"}.get(name, name),
                    item_order=number,
                )
                db.add(question)
                db.flush()
                db.add(QuestionVariant(
                    canonical_question_id=question.id, questionnaire_id=forms[form],
                    question_number=f"Q{number}", question=f"{name} question {number}",
                    gender_form="male", file_name=name,
                ))
        db.commit()
        yield db, path
    engine.dispose()


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_preview_writes_nothing(scoring_data):
    db, path = scoring_data
    result = import_scoring_workbook(db, path)
    assert result["response_value_labels"] == {"new": 32, "existing": 0}
    assert result["questionnaire_scoring_rules"]["new"] == 9
    assert result["scoring_rule_questions"]["new"] == 10
    assert not db.new and not db.dirty
    for model in (ResponseValueLabel, QuestionnaireScoringRule, ScoringRuleQuestion):
        assert count(db, model) == 0


@pytest.mark.parametrize("shared_heading", [True, False])
def test_binary_options_import_and_repeat(scoring_data, shared_heading):
    db, path = scoring_data
    workbook = load_workbook(path)
    sheet = workbook["STAI-T"]
    sheet.title = "AQ"
    scores = [0, 0, 1, 1]
    for column, score in enumerate(scores, 4):
        suffix = "0/1" if shared_heading else str(score)
        sheet.cell(1, column, f"Choice {column - 3} ({suffix})")
        sheet.cell(2, column, score)
    rules = workbook["STAI-T_scoring_rules"]
    rules.title = "AQ_scoring_rules"
    rules.append(["AQ", "total", "total", "sum", None, 0, 1])
    workbook.save(path)
    workbook.close()
    question = db.scalar(select(CanonicalQuestion).where(CanonicalQuestion.code == "STAI-T_1"))
    question.test_psicolog = "AQ"
    db.commit()

    assert import_scoring_workbook(db, path)["response_value_labels"]["new"] == 32
    assert count(db, ResponseValueLabel) == 0
    import_scoring_workbook(db, path, apply=True)
    db.commit()
    question = db.scalar(select(CanonicalQuestion).where(CanonicalQuestion.code == "STAI-T_1"))
    labels = db.scalars(select(ResponseValueLabel).where(
        ResponseValueLabel.question_id == question.id,
    ).order_by(ResponseValueLabel.option_position)).all()
    assert [label.numeric_value for label in labels] == scores
    assert [label.text_male for label in labels] == [f"Choice {n}" for n in range(1, 5)]
    assert all(result["new"] == 0 for result in import_scoring_workbook(db, path).values())
    labels[0].numeric_value = 1
    db.commit()
    with pytest.raises(ValueError, match="AQ item 1.*conflicts"):
        import_scoring_workbook(db, path, apply=True)


@pytest.mark.parametrize("invalid_score", [None, 2, True, "0"])
def test_binary_options_reject_invalid_scores(scoring_data, invalid_score):
    _, path = scoring_data
    workbook = load_workbook(path)
    sheet = workbook["STAI-T"]
    sheet.title = "AQ"
    for column, score in enumerate([0, 0, 1, 1], 4):
        sheet.cell(1, column, f"Choice {column - 3} (0/1)")
        sheet.cell(2, column, score)
    sheet["D2"] = invalid_score
    workbook.save(path)
    workbook.close()
    with pytest.raises(ValueError, match="invalid scores"):
        read_questionnaire_sheet("AQ", path)


@pytest.mark.parametrize("duplicate_headers", [True, False])
def test_non_aq_rejects_duplicate_scores(scoring_data, duplicate_headers):
    _, path = scoring_data
    workbook = load_workbook(path)
    sheet = workbook["STAI-T"]
    if duplicate_headers:
        sheet["E1"] = "Choice 2 (1)"
    else:
        sheet["E2"] = 1
    workbook.save(path)
    workbook.close()
    with pytest.raises(ValueError, match="duplicate answer scores|invalid scores"):
        read_questionnaire_sheet("STAI-T", path)


def test_import_links_subscales_parents_and_repeats(scoring_data):
    db, path = scoring_data
    import_scoring_workbook(db, path, apply=True)
    db.commit()
    result = import_scoring_workbook(db, path, apply=True)
    assert all(value["new"] == 0 for value in result.values())
    assert result["response_value_labels"]["existing"] == 32
    rules = {(r.test_name, r.rule_code): r for r in db.scalars(select(QuestionnaireScoringRule))}
    assert rules[("PHQ", "positive")].parent_rule_id == rules[("PHQ", "anxiety")].id
    assert rules[("PSS", "low")].parent_rule_id == rules[("PSS", "total")].id
    goals = rules[("DERS", "goals")]
    links = db.scalars(select(ScoringRuleQuestion).where(ScoringRuleQuestion.rule_id == goals.id)).all()
    assert [link.source_question_number for link in links] == [1]
    assert count(db, ScoringRuleQuestion) == 10
    question = db.scalar(select(CanonicalQuestion).where(CanonicalQuestion.code == "PSS_1"))
    label = db.scalar(select(ResponseValueLabel).where(
        ResponseValueLabel.question_id == question.id, ResponseValueLabel.option_position == 1,
    ))
    assert label.numeric_value == 4


def test_conflicting_label_prevents_all_staging(scoring_data):
    db, path = scoring_data
    item = read_and_match_all(db, path)["PSS"][0]
    db.add(ResponseValueLabel(
        question_id=item["question_id"], option_position=1, numeric_value=4,
        text_male="Different", text_female="Different", source_sheet="PSS", source_row=2,
    ))
    db.commit()
    with pytest.raises(ValueError, match="PSS item 1.*conflicts"):
        import_scoring_workbook(db, path, apply=True)
    assert not db.new and not db.dirty
    assert count(db, QuestionnaireScoringRule) == 0
    assert count(db, ResponseValueLabel) == 1


def test_missing_parent_is_rejected(scoring_data):
    db, path = scoring_data
    workbook = load_workbook(path)
    workbook["PHQ4_scoring_rules"]["K5"] = "missing"
    workbook.save(path)
    workbook.close()
    with pytest.raises(ValueError, match="Missing scoring parent"):
        read_scoring_rules(read_and_match_all(db, path), path)


def test_changed_source_row_does_not_conflict(scoring_data):
    db, path = scoring_data
    import_scoring_workbook(db, path, apply=True)
    db.commit()
    label = db.scalar(select(ResponseValueLabel))
    label.source_row = 99
    db.commit()
    assert import_scoring_workbook(db, path)["response_value_labels"]["new"] == 0
    assert label.source_row == 99


def test_new_test_options_questionnaire_and_metadata(scoring_data):
    db, path = scoring_data
    questionnaire = Questionnaire(code="follow-up", name="Follow-up")
    db.add(questionnaire)
    db.flush()
    question = CanonicalQuestion(
        questionnaire_id=questionnaire.id, code="new_item", test_psicolog="new-instrument", item_order=1,
    )
    db.add(question)
    db.flush()
    db.add(QuestionVariant(
        canonical_question_id=question.id, questionnaire_id=questionnaire.id,
        question_number="Q1", question="A new question", gender_form="male", file_name="Future",
    ))
    db.commit()
    scores = [-9, -4, 0, 2, 8, 10, 30]
    workbook = load_workbook(path)
    sheet = workbook.create_sheet("Future")
    sheet.append(["question_text", "item_number", "questionnaire_code"] +
                 [f"Choice {n} ({score})" for n, score in enumerate(scores)])
    sheet.append(["A new question", 1, "follow-up", *reversed(scores)])
    workbook.save(path)
    # A new question sheet can be imported before scoring rules are supplied.
    assert import_scoring_workbook(db, path)["response_value_labels"]["new"] == 39
    rules = workbook.create_sheet("Future_scoring_rules")
    headers = [cell.value for cell in workbook["PSS_scoring_rules"][1]]
    rules.append([*headers, "description_he", "notes", "is_enabled"])
    rules.append(["Future", "total", "total", "sum", None, -9, 30,
                  None, None, None, None, "Description", "Study note", False])
    workbook.save(path)
    workbook.close()
    import_scoring_workbook(db, path, apply=True)
    db.commit()
    rule = db.scalar(select(QuestionnaireScoringRule).where(QuestionnaireScoringRule.test_name == "new-instrument"))
    assert (rule.description_he, rule.notes, rule.is_enabled) == ("Description", "Study note", False)
    assert count(db, ResponseValueLabel) == 39
    assert all(value["new"] == 0 for value in import_scoring_workbook(db, path).values())


@pytest.mark.parametrize("sheet_name", ["PSS", "PSS_scoring_rules"])
def test_unknown_metadata_is_reported(scoring_data, sheet_name):
    db, path = scoring_data
    workbook = load_workbook(path)
    sheet = workbook[sheet_name]
    sheet.cell(1, sheet.max_column + 1, "new_metadata")
    sheet.cell(2, sheet.max_column, "Must not be lost")
    workbook.save(path)
    workbook.close()
    with pytest.raises(ValueError, match="unsupported columns.*new_metadata"):
        import_scoring_workbook(db, path, apply=True)
    assert not db.new and not db.dirty


def test_ambiguous_wording_requires_explicit_test_name(scoring_data):
    db, path = scoring_data
    original = db.scalar(select(CanonicalQuestion).where(CanonicalQuestion.code == "PSS_1"))
    duplicate = CanonicalQuestion(
        questionnaire_id=original.questionnaire_id, code="duplicate", test_psicolog="Other", item_order=1,
    )
    db.add(duplicate)
    db.flush()
    db.add(QuestionVariant(
        canonical_question_id=duplicate.id, questionnaire_id=original.questionnaire_id,
        question_number="Q99", question="PSS question 1", gender_form="male", file_name="Other",
    ))
    db.commit()
    with pytest.raises(ValueError, match="Expected one Hebrew match"):
        import_scoring_workbook(db, path)
    workbook = load_workbook(path)
    sheet = workbook["PSS"]
    column = sheet.max_column + 1
    sheet.cell(1, column, "test_name")
    for row in range(2, sheet.max_row + 1):
        sheet.cell(row, column, "PSS")
    workbook.save(path)
    workbook.close()
    assert import_scoring_workbook(db, path)["response_value_labels"]["new"] == 32

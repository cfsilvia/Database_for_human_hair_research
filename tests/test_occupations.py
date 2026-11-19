from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.analysis.occupations import (
    add_occupation_values, get_occupation_values, occupation_key,
    occupation_answers_match, occupation_labels_equal,
)
from app.database.models import Occupation, OccupationOverride, Participant


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Occupation.__table__.create(engine)
    Participant.__table__.create(engine)
    OccupationOverride.__table__.create(engine)

    with Session(engine) as session:
        for code, name, major, first, second in (
            ("Y242", "Students", "Y", "Y2", "Y24"),
            ("2512", "Software developers", "2", "25", "251"),
            ("2519", "Software developers", "2", "25", "251"),
            ("1111", "Shared name", "1", "11", "111"),
            ("2111", "Shared name", "2", "21", "211"),
            ("0110", "Army officer", "0", "01", "011"),
            ("2131", "Research biologists", "2", "21", "213"),
            ("2112", "Research physicists", "2", "21", "211"),
            ("2514", "מתכנתים", "2", "25", "251"),
        ):
            session.add(Occupation(
                occupation_code=code,
                occupation_he=name,
                major_code=major,
                major_group_he=f"Major {major}",
                first_group_code=first,
                first_group_he=f"First {first}",
                second_group_code=second,
                second_group_he=f"Second {second}",
            ))
        session.commit()
        yield session

    engine.dispose()


@pytest.mark.parametrize("answer, expected", [
    ("סטודנט", ("Y", "Y2", "Y24")),
    ("  סטודנטית  ", ("Y", "Y2", "Y24")),
    (" SOFTWARE   developers ", ("2", "25", "251")),
    ("Army officer", ("0", "01", "011")),
    ("Shared name", ("Unknown",) * 3),
    ("Software developer", ("2", "25", "251")),
    ("Software developper", ("2", "25", "251")),
    ("Software-developers", ("2", "25", "251")),
    ("Research", ("2", "21", "Unknown")),
    ("מתכנתת", ("2", "25", "251")),
    ("מתכנת", ("2", "25", "251")),
    ("עובדת", ("Unknown",) * 3),
    ("סטודנטית לביולוגיה", ("Unknown",) * 3),
    ("סטודנט ומתכנת", ("Unknown",) * 3),
    (None, ("Unknown",) * 3),
    ("   ", ("Unknown",) * 3),
])
def test_occupation_matching(db, answer, expected):
    result = get_occupation_values(db, {101: answer})[101]

    assert tuple(result[field] for field in (
        "major_code", "first_group_code", "second_group_code",
    )) == expected
    for level in ("major", "first_group", "second_group"):
        label_field = "major_group_he" if level == "major" else f"{level}_he"
        code = result[f"{level}_code"]
        prefix = {"major": "Major", "first_group": "First", "second_group": "Second"}[level]
        assert result[label_field] == ("Unknown" if code == "Unknown" else f"{prefix} {code}")
    assert not db.new and not db.dirty


def test_student_alias_without_reference(db):
    db.delete(db.get(Occupation, "Y242"))
    db.commit()

    result = get_occupation_values(db, {101: "סטודנטית"})[101]

    assert set(result.values()) == {"Unknown"}


def test_occupation_key():
    assert occupation_key("  SOFTWARE \t Developers ") == "software developers"
    assert occupation_key(None) == ""
    assert occupation_key("Software/developers") == "software developers"


def test_conflicting_question_variants_are_unknown(db):
    questions = [
        SimpleNamespace(canonical_id=1, question="?מהו העיסוק שלך"),
        SimpleNamespace(canonical_id=2, question="מהו העיסוק שלך?"),
    ]
    rows = [{
        "subject_id": 101,
        "canonical_1": "סטודנטית",
        "canonical_2": "Software developers",
    }]
    labels = {}

    add_occupation_values(db, rows, questions, labels)

    assert rows[0]["occupation_second_group"] == "Unknown"
    assert rows[0]["canonical_1"] == "סטודנטית"
    assert rows[0]["canonical_2"] == "Software developers"
    assert labels == {}


@pytest.mark.parametrize("left,right,expected", [
    ("Unknown", "בעלי משלח יד לא ידוע", True),
    (None, "לא ניתן לקבוע", True),
    ("  ", "Unknown", True),
    ("Role\nRole", "Role", True),
    ("Role A\nRole B", "Role B\nRole A", True),
    ("Role A\nRole B", "Role A", False),
])
def test_classification_comparison(left, right, expected):
    assert occupation_labels_equal(left, right) is expected


def test_answer_comparison_preserves_punctuation():
    assert occupation_answers_match("  SOFTWARE\n developer ", "Software developer")
    assert not occupation_answers_match("A/B", "A B")
    assert not occupation_answers_match(None, "")


@pytest.mark.parametrize("answer,source", [
    (" SOFTWARE   developers ", "AI"),
    ("Army officer", "Automatic"),
    (None, "Automatic"),
])
def test_saved_override_is_specific_to_participant_and_answer(db, answer, source):
    db.add(Participant(subject_id=101))
    db.flush()
    db.add(OccupationOverride(
        subject_id=101, occupation_answer="Software developers",
        major_code="2", major_group_he="Major 2",
        first_group_code="לא ניתן לקבוע", first_group_he="לא ניתן לקבוע",
        second_group_code="לא ניתן לקבוע", second_group_he="לא ניתן לקבוע",
        review="תחום לא צוין; נדרשת בדיקה.", source_filename="comparison.xlsx",
    ))
    db.commit()
    rows = [
        {"subject_id": 101, "canonical_1": answer},
        {"subject_id": 102, "canonical_1": "Software developers"},
    ]
    labels = {}
    comparisons = add_occupation_values(
        db, rows, [SimpleNamespace(canonical_id=1, question="מהו העיסוק שלך?")], labels,
    )
    assert rows[0]["occupation_source"] == source
    assert rows[1]["occupation_source"] == "Automatic"
    assert rows[1]["occupation_second_group"] == "251"
    assert "102" not in comparisons
    if source == "AI":
        assert rows[0]["occupation_first_group"] == "לא ניתן לקבוע"
        assert comparisons["101"]["different_columns"] == [
            "occupation_first_group", "occupation_second_group",
        ]
        assert rows[0]["occupation_review"].startswith("תחום לא צוין; נדרשת בדיקה.")
        assert labels["101"]["occupation_first_group"] == "לא ניתן לקבוע"
    else:
        assert "101" not in comparisons
        assert "needs updating" in rows[0]["occupation_review"]


def test_conflicting_answers_disable_saved_override(db):
    db.add(Participant(subject_id=101))
    db.flush()
    db.add(OccupationOverride(
        subject_id=101, occupation_answer="Software developers",
        major_code="2", major_group_he="Major 2", first_group_code="25",
        first_group_he="First 25", second_group_code="251", second_group_he="Second 251",
        review="", source_filename="comparison.xlsx",
    ))
    db.commit()
    rows = [{"subject_id": 101, "canonical_1": "Software developers", "canonical_2": "Army officer"}]
    comparisons = add_occupation_values(db, rows, [
        SimpleNamespace(canonical_id=i, question="מהו העיסוק שלך?") for i in (1, 2)
    ], {})
    assert comparisons == {}
    assert rows[0]["occupation_source"] == "Automatic"
    assert rows[0]["occupation_major"] == "Unknown"
    assert "needs updating" in rows[0]["occupation_review"]

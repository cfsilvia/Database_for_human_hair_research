import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    CanonicalQuestion,
    Questionnaire,
    QuestionVariant,
)




'''
function to find questionnaire
'''
def get_or_create_questionnaire(
    db, questionnaire_code: str,):
    questionnaire_code = str(questionnaire_code).strip()

    questionnaire = db.scalar(select(Questionnaire).where(Questionnaire.code== questionnaire_code))

    if questionnaire is None:
        questionnaire = Questionnaire(code=questionnaire_code,name=questionnaire_code,)
        db.add(questionnaire)
        db.flush()

    return questionnaire

'''
function to create/find canonical question
The corresponding female row finds the same record rather than creating another one.
'''
def get_or_create_canonical_question(
    db,
    questionnaire_id: int,
    code: str,
    test_name: str,
    item_order: int,
):
    question = db.scalar(
        select(CanonicalQuestion).where(
            CanonicalQuestion.questionnaire_id
            == questionnaire_id,

            CanonicalQuestion.test_psicolog
            == test_name,

            CanonicalQuestion.item_order
            == item_order,
        )
    )

    if question is None:

        question = CanonicalQuestion(
            questionnaire_id=questionnaire_id,
            code=code,
            test_psicolog=test_name,
            item_order=item_order,
        )

        db.add(question)
        db.flush()

    return question

'''
Function to check wether variant already exists
'''
def get_question_variant(db, questionnaire_id: int, question_number: str, gender_form: str, file_name: str,):
    return db.scalar(
        select(QuestionVariant).where(
            QuestionVariant.questionnaire_id
            == questionnaire_id,

            QuestionVariant.question_number
            == question_number,

            QuestionVariant.gender_form
            == gender_form,

            QuestionVariant.file_name
            == file_name,
        )
    )

    
'''
helper for excel nan
    '''
def clean_value(value):
     if pd.isna(value):
        return None

     return value
'''
helper to normalize to Q numbers
'''
def normalize_question_number(value):
    if pd.isna(value):
        return None

    value = str(value).strip() #strip removes blank spacess

    if value.lower().startswith("q"):
        value = "Q" + value[1:]

    return value
'''
helper that converts one metadata row into the new structure
'''
def get_question_fields(row):
    parent_number = normalize_question_number(row["number question"])
    parent_text = clean_value(row["question"])
    sub_number = normalize_question_number(row.get("subquestion number"))
    sub_text = clean_value(row.get("subquestion"))

    # Normal question or main Answer field # Example:
    # number question = Q5
    # subquestion number = Q5
    if (sub_number is None or sub_number == parent_number):
        return {
            "question_number": parent_number,
            "question": parent_text,
            "parent_question_number": None,
            "parent_question": None,
        }

    # Real child/follow-up question:#
    # Q12.1
    # Q5.other
    # Q13.detail
    return {
        "question_number": sub_number,
        "question": sub_text,
        "parent_question_number": parent_number,
        "parent_question": parent_text,
    }



'''
    Import one metadata dataframe
    '''
def import_metadata_dataframe(db, df: pd.DataFrame,):
    variants_created = 0
    variants_existing = 0

    for _, row in df.iterrows():

        questionnaire =  get_or_create_questionnaire(db,row["questionnaire"],)

        item_order = int(row["item_order"])

        canonical = get_or_create_canonical_question(db=db, questionnaire_id=questionnaire.id, code=row["canonical_question"],
            test_name=row["file name"],
            item_order=item_order,
        )

        question_fields = get_question_fields(row)

        existing = get_question_variant(db=db, questionnaire_id=questionnaire.id, question_number=question_fields["question_number"],
        gender_form=row["gender_form"],
        file_name=row["file name"],)

        if existing is not None:
          variants_existing += 1
          continue

        variant = QuestionVariant(canonical_question_id=canonical.id, questionnaire_id=questionnaire.id,
                 question_number=question_fields["question_number"], question=question_fields["question"],
        parent_question_number=question_fields["parent_question_number"],parent_question=question_fields["parent_question"],
        gender_form=row["gender_form"],file_name=row["file name"],
        pair_status=clean_value(row["pair_status"]),pair_similarity=clean_value(row["pair_similarity"]),)

        db.add(variant)

        variants_created += 1

    db.commit()

    return {
        "variants_created": variants_created,
        "variants_existing": variants_existing,
    }
    
    
'''
Read every sheet from you metadata workbook
'''

def import_metadata_workbook(db,excel_path,):
    excel = pd.ExcelFile(excel_path)

    results = {}

    for sheet_name in excel.sheet_names:

        df = pd.read_excel(excel_path,sheet_name=sheet_name,)

        result = import_metadata_dataframe(db=db,df=df,)

        results[sheet_name] = result

    return results
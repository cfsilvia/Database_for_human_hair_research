from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.importers.question_metadata import build_question_metadata
from app.importers.canonical_mapper import assign_canonical_questions
from app.importers.metadata_exporter import (save_metadata_by_test,)




df_questions = build_question_metadata(
    data_folder="D:\\Database_for_human_hair_research\\data\\data_of_questionaries",
    output_file="questions.xlsx",
)
df_questions = assign_canonical_questions(
    df_questions
)

save_metadata_by_test(df=df_questions, output_file="D:\\Database_for_human_hair_research\\data\\question_metadata.xlsx",)


print(df_questions)
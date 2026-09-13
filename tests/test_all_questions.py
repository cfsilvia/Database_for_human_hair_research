from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.importers.question_metadata import build_question_metadata


df_questions = build_question_metadata(
    data_folder="D:\\Silvia\\Hair_project\\API\\Database_for_human_hair_research\\data\\data_of_questionaries",
    output_file="questions.xlsx",
)

print(df_questions)

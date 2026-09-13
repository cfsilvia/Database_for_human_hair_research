from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from app.importers.excel_reader import read_excel_file
from app.importers.validator import validate_import

df, metadata = read_excel_file(
    "data/incoming/שאלון1_030926.xlsx")

validate_import(df)

#print(metadata)

#print(df.head())
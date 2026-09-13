from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.importers.excel_reader import get_excel_file

df = get_excel_file("data/incoming/שאלון1_030926.xlsx")

print(df.shape)
print(df.columns.tolist())
print(df.head())

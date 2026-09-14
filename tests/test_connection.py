from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


from app.database.connection import test_connection

result = test_connection()

print("Database:", result[0])
print("User:", result[1])
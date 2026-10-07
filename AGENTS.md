# AGENTS.md

## Repo shape
- FastAPI entrypoint is `app.main:app`; static UI lives in `app/static/`.
- PostgreSQL config comes from `.env` as `DATABASE_URL`; importing `app.database.connection` or `app.main` requires it.
- Alembic uses `app.config.settings.database_url` in `alembic/env.py`, overriding the placeholder in `alembic.ini`.
- SQLAlchemy models are in `app/database/models.py`; keep model and Alembic migration changes synchronized.

## Environment and commands
- Prefer the Conda env from `environment.yml`: `conda env create -f environment.yml`, then `conda activate hair_database`.
- `requirements.txt` contains local Windows/Conda build URLs, so it is less portable than `environment.yml`.
- Run the app from repo root with `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`; `start_server.bat` does the same on this machine.
- After `.env` is set, apply schema with `alembic upgrade head`.

## Tests
- Run focused self-contained tests with `python -m pytest tests/test_validator.py tests/test_subject_id_corrector.py`.
- Avoid running all of `tests/` blindly: several files execute work at import time and depend on local PostgreSQL or hard-coded/missing Excel paths.
- Single-test example: `python -m pytest tests/test_validator.py::ValidateImportReportTests::test_writes_report_with_actual_excel_cells`.

## Import/data workflows
- Use `read_questionnaire_file()` for incoming questionnaire exports; it reads two header rows and starts data at Excel row 3. Do not replace it with plain `pd.read_excel` for questionnaire imports.
- DB load order matters: `alembic upgrade head` -> metadata/questionnaires -> participants -> sessions -> responses.
- Sessions require an existing `Questionnaire`; responses require existing `Participant`, `QuestionnaireSession`, and `QuestionVariant`.
- Current scripts are hard-coded for the second questionnaire files/code in `data/incoming`; update those constants deliberately before importing other questionnaires.
- `validate_import()` writes `data/validation_results.xlsx` by default; pass `output_path=None` when experimenting without writing a report.

## Data and secrets
- Preserve Hebrew filenames and Unicode paths under `data/`.
- `.env` is ignored and must not be committed.

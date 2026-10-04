import pandas as pd
from sqlalchemy import select

from app.database.models import Participant


def import_participants(
    db, df: pd.DataFrame, subject_id_column: str = "subject id",):
    created = 0
    existing = 0
    skipped = 0

    if subject_id_column not in df.columns:
        raise ValueError(
            f"Column '{subject_id_column}' not found."
        )

    for subject_id in df[subject_id_column]:

        if pd.isna(subject_id):
            skipped += 1
            continue

        subject_id = int(subject_id)

        participant = db.scalar(select(Participant).where(Participant.subject_id == subject_id))

        if participant is not None:
            existing += 1
            continue

        participant = Participant(subject_id=subject_id)

        db.add(participant)
        db.flush()

        created += 1

    db.commit()

    return {
        "created": created,
        "existing": existing,
        "skipped": skipped,
    }
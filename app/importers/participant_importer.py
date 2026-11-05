
import pandas as pd
from sqlalchemy import select

from app.database.models import Participant


def import_participants(
    db,
    df: pd.DataFrame,
    subject_id_column: str = "subject id",
):
    created = 0
    existing = 0
    skipped = 0

    if subject_id_column not in df.columns:
        raise ValueError(
            f"Column '{subject_id_column}' not found."
        )

    seen = set()

    for value in df[subject_id_column]:

        if pd.isna(value):
            skipped += 1
            continue

        subject_id = int(value)

        if subject_id in seen:
            skipped += 1
            continue

        seen.add(subject_id)

        participant = db.scalar(
            select(Participant).where(
                Participant.subject_id == subject_id
            )
        )

        if participant is not None:
            existing += 1
            continue

        participant = Participant(subject_id=subject_id)

        db.add(participant)
        db.flush()

        created += 1

    # The calling script is responsible for db.commit()

    return {
        "created": created,
        "existing": existing,
        "skipped": skipped,
    }

import pandas as pd
from sqlalchemy import select

from app.database.models import Participant, Questionnaire,QuestionnaireSession

def get_questionnaire(db, questionnaire_code: str):
    return db.scalar(
        select(Questionnaire).where(
            Questionnaire.code == questionnaire_code
        )
    )

def session_exists(db, participant_id: int, questionnaire_id: int,):
    return db.scalar(
        select(QuestionnaireSession).where(
            QuestionnaireSession.participant_id == participant_id,
            QuestionnaireSession.questionnaire_id == questionnaire_id,
        )
    )
    
def import_sessions(
    db,
    df: pd.DataFrame,
    questionnaire_code: str,
    subject_id_column: str = "subject id",
    started_column: str = "started",
    ended_column: str = "ended",
    score_column: str = "score",
):
    
   questionnaire = get_questionnaire(db,questionnaire_code)
   
   if questionnaire is None:
        raise ValueError(
            f"Questionnaire '{questionnaire_code}' not found in database.")
            
   created = 0
   existing = 0
   skipped = 0
   
   for _, row in df.iterrows():

        subject_id = row.get(subject_id_column)

        if pd.isna(subject_id):
            skipped += 1
            continue
        
        subject_id = int(subject_id)

        participant = db.scalar(
            select(Participant).where(
                Participant.subject_id == subject_id
            )
        )
        if participant is None:
            skipped += 1
            continue
        
        existing_session = session_exists(db, participant_id=participant.id, questionnaire_id=questionnaire.id)
        if existing_session is not None:
            existing += 1
            continue
        
        session = QuestionnaireSession(
            participant_id=participant.id,
            questionnaire_id=questionnaire.id,
            started_at=row.get(started_column),
            ended_at=row.get(ended_column),
            score=row.get(score_column),
        )

        db.add(session)
        db.flush()
        created += 1

   db.commit()
   
   return {
        "created": created,
        "existing": existing,
        "skipped": skipped,
    }
    
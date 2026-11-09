from sqlalchemy import text


# Input: db - an open SQLAlchemy database session.
# Output: a dictionary of counts for either, first, second, and both questionnaires,
# plus male/female wording counts among participants who answered both.
def get_participation_summary(db):
    """Count participation and selected wording among those who answered both."""
    query = text("""
        WITH participation AS (
            SELECT
                s.participant_id,
                BOOL_OR(q.code = 'first-questionnaire') AS answered_first,
                BOOL_OR(q.code = 'second-questionnaire') AS answered_second,
                MAX(s.wording_form) AS wording
            FROM questionnaire_sessions s
            JOIN questionnaires q ON q.id = s.questionnaire_id
            WHERE q.code IN ('first-questionnaire', 'second-questionnaire')
              AND (
                  s.ended_at IS NOT NULL
                  OR EXISTS (
                      SELECT 1 FROM responses r
                      WHERE r.session_id = s.id
                        AND (
                            r.value_numeric IS NOT NULL
                            OR TRIM(r.value_text) <> ''
                        )
                  )
              )
            GROUP BY s.participant_id
        )
        SELECT
            COUNT(*) AS answered_any,
            COUNT(*) FILTER (WHERE answered_first) AS answered_first,
            COUNT(*) FILTER (WHERE answered_second) AS answered_second,
            COUNT(*) FILTER (
                WHERE answered_first AND answered_second
            ) AS answered_both,
            COUNT(*) FILTER (
                WHERE answered_first AND answered_second AND wording = 'male'
            ) AS males_both,
            COUNT(*) FILTER (
                WHERE answered_first AND answered_second AND wording = 'female'
            ) AS females_both
        FROM participation
    """)

    return dict(db.execute(query).mappings().one())

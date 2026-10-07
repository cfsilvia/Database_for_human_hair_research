SELECT
    p.subject_id,
    q.code AS questionnaire,
    qs.id AS session_id
FROM questionnaire_sessions qs
JOIN participants p
    ON qs.participant_id = p.id
JOIN questionnaires q
    ON qs.questionnaire_id = q.id
WHERE p.subject_id = 10
ORDER BY q.code;
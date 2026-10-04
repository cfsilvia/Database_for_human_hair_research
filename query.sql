SELECT
    p.subject_id,
    q.code AS questionnaire,

    cq.test_psicolog AS test,

    qv.gender_form,

    qv.question_number,
    qv.question,

    qv.parent_question_number,
    qv.parent_question,

    r.value_numeric,
    r.value_text

FROM responses AS r

JOIN questionnaire_sessions AS qs
    ON r.session_id = qs.id

JOIN participants AS p
    ON qs.participant_id = p.id

JOIN questionnaires AS q
    ON qs.questionnaire_id = q.id

JOIN question_variants AS qv
    ON r.question_variant_id = qv.id

JOIN canonical_questions AS cq
    ON qv.canonical_question_id = cq.id

WHERE p.subject_id = 10

ORDER BY
    q.code,
    CAST(
        SUBSTRING(qv.question_number FROM '\d+')
        AS INTEGER
    ),
    qv.question_number;
async function getParticipant(subjectId) {

    const response = await fetch(
        `/api/participants/${subjectId}`
    );

    if (!response.ok) {
        throw new Error(
            "Participant not found"
        );
    }

    return await response.json();
}

async function getParticipantResponses(
    subjectId
) {

    const response = await fetch(
        `/api/participants/${subjectId}/responses`
    );

    if (!response.ok) {
        throw new Error(
            "Could not load participant responses"
        );
    }

    return await response.json();
}

async function getDatabaseSummary() {

    const response = await fetch(
        "/api/summary-test"
    );

    if (!response.ok) {
        throw new Error(
            "Could not load database summary"
        );
    }

    return await response.json();
}
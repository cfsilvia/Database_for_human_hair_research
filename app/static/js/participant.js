function naturalQuestionSort(a, b) {

    if (!a || !b) {
        return 0;
    }

    const numberA =
        parseInt(
            a.match(/\d+/)?.[0] ?? 0
        );

    const numberB =
        parseInt(
            b.match(/\d+/)?.[0] ?? 0
        );

    if (numberA !== numberB) {
        return numberA - numberB;
    }

    return a.localeCompare(
        b,
        undefined,
        { numeric: true }
    );
}



async function searchParticipant() {

    const subjectIdInput =
        document.getElementById(
            "subjectId"
        );

    const message =
        document.getElementById(
            "searchMessage"
        );

    const participantSection =
        document.getElementById(
            "participantSection"
        );

    const subjectId =
        subjectIdInput.value;


    if (!subjectId) {

        message.textContent =
            "Please enter a Subject ID.";

        participantSection.classList.add(
            "hidden"
        );

        return;
    }


    message.textContent =
        "Searching...";


    try {

        const participant =
            await getParticipant(
                subjectId
            );


        showParticipant(
            participant
        );


        message.textContent = "";

    }

    catch (error) {

        message.textContent =
            error.message;

        participantSection.classList.add(
            "hidden"
        );

    }

}


function showParticipant(participant) {

    const participantSection =
        document.getElementById(
            "participantSection"
        );

    const subjectIdElement =
        document.getElementById(
            "participantSubjectId"
        );


    subjectIdElement.textContent =
        participant.subject_id;


    participantSection.classList.remove(
        "hidden"
    );
}

function showParticipantResponses() {

    const subjectId =
        document.getElementById(
            "participantSubjectId"
        ).textContent;

    if (!subjectId) {
        return;
    }

    window.location.href =
        `/static/responses.html?subject_id=${encodeURIComponent(subjectId)}`;
}

function showResponses(responses) {

    const responsesSection =
        document.getElementById(
            "responsesSection"
        );

    const tableBody =
        document.getElementById(
            "responsesTableBody"
        );

    tableBody.innerHTML = "";

    // Detect participant gender from answered questions
    const answeredGenderRow = responses.find(item =>
        (item.gender_form === "male" || item.gender_form === "female") &&
        (
            item.value_numeric !== null ||
            (item.value_text !== null && item.value_text !== "")
        )
    );

    const participantGender =
        answeredGenderRow?.gender_form;

    // Keep only questions for the participant's gender
    if (participantGender) {
        responses = responses.filter(item =>
            !item.gender_form ||
            item.gender_form === participantGender
        );
    }


    // Sort by questionnaire, then question number
    responses.sort((a, b) => {

        if (a.questionnaire !== b.questionnaire) {
            return a.questionnaire.localeCompare(
                b.questionnaire
            );
        }

        return naturalQuestionSort(
            a.question_number,
            b.question_number
        );
    });


    for (const item of responses) {

        const row =
            document.createElement("tr");

        row.innerHTML = `
            <td>${item.questionnaire ?? ""}</td>
            <td>${item.test ?? ""}</td>
            <td>${item.gender_form ?? ""}</td>
            <td>${item.question_number ?? ""}</td>
            <td>${item.parent_question ?? ""}</td>
            <td>${item.question ?? ""}</td>
            <td>${item.value_numeric ?? ""}</td>
            <td>${item.value_text ?? ""}</td>
        `;

        tableBody.appendChild(row);
    }

    responsesSection.classList.remove(
        "hidden"
    );
}
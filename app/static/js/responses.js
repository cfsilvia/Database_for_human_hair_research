document.addEventListener(
    "DOMContentLoaded",
    loadResponsesPage
);


async function loadResponsesPage() {

    const params =
        new URLSearchParams(
            window.location.search
        );

    const subjectId =
        params.get("subject_id");


    const subjectIdDisplay =
        document.getElementById(
            "subjectIdDisplay"
        );

    const message =
        document.getElementById(
            "responsesMessage"
        );

    const table =
        document.getElementById(
            "responsesTable"
        );


    if (!subjectId) {

        message.textContent =
            "No Subject ID was provided.";

        return;
    }


    subjectIdDisplay.textContent =
        subjectId;


    document.getElementById(
        "backButton"
    ).addEventListener(
        "click",
        function () {
            window.location.href = "/";
        }
    );


    try {

        const responseData =
            await getParticipantResponses(
                subjectId
            );

        let responses =
            responseData.responses;


        // -----------------------------------------
        // Detect participant gender
        // -----------------------------------------

        const answeredGenderRow =
            responses.find(item =>

                (
                    item.gender_form === "male" ||
                    item.gender_form === "female"
                )

                &&

                (
                    item.value_numeric !== null ||

                    (
                        item.value_text !== null &&
                        item.value_text !== ""
                    )
                )
            );


        const participantGender =
            answeredGenderRow?.gender_form;


        // -----------------------------------------
        // Remove questions for opposite gender
        // -----------------------------------------

        if (participantGender) {

            responses =
                responses.filter(item =>

                    !item.gender_form ||

                    item.gender_form ===
                        participantGender
                );
        }


        // -----------------------------------------
        // Sort questionnaire + question number
        // -----------------------------------------

        responses.sort((a, b) => {

            if (
                a.questionnaire !==
                b.questionnaire
            ) {

                return (
                    a.questionnaire ?? ""
                ).localeCompare(
                    b.questionnaire ?? ""
                );
            }


            return naturalQuestionSort(
                a.question_number,
                b.question_number
            );
        });


        // -----------------------------------------
        // Draw table
        // -----------------------------------------

        const tableBody =
            document.getElementById(
                "responsesTableBody"
            );


        tableBody.innerHTML = "";


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


        message.textContent = "";

        table.classList.remove(
            "hidden"
        );

    }

    catch (error) {

        console.error(error);

        message.textContent =
            error.message;
    }
}



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
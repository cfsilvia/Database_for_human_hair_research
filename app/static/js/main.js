document.addEventListener(
    "DOMContentLoaded",
    function () {

        const searchButton =
            document.getElementById(
                "searchButton"
            );

        searchButton.addEventListener(
            "click",
            searchParticipant
        );

        const responsesButton =
            document.getElementById(
                "responsesButton"
            );

        responsesButton.addEventListener(
            "click",
            showParticipantResponses
        );

        // -----------------------------------------
        // Load database summary
        // -----------------------------------------

        loadDatabaseSummary();

    }
);

// =========================================================
// DATABASE SUMMARY
// =========================================================

async function loadDatabaseSummary() {

    try {

        const summary =
            await getDatabaseSummary();


        // Participants
        document.getElementById(
            "participantsCount"
        ).textContent =
            summary.participants;


        // Males
        document.getElementById(
            "malesCount"
        ).textContent =
            summary.males;


        // Females
        document.getElementById(
            "femalesCount"
        ).textContent =
            summary.females;

    }

    catch (error) {

        console.error(
            "Could not load database summary:",
            error
        );

    }
}
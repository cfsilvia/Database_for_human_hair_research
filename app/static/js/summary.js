document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("summaryLink").addEventListener("click", function (event) {
        event.preventDefault();
        loadParticipationSummary();
    });
});


// Load current counts and show the summary instead of the participants table.
async function loadParticipationSummary() {
    document.getElementById("participantsTableSection").classList.add("hidden");
    document.getElementById("summarySection").classList.remove("hidden");
    document.getElementById("summaryContent").classList.add("hidden");
    setActiveSidebarLink("summaryLink");
    const message = document.getElementById("summaryMessage");
    message.textContent = "Loading summary...";

    try {
        const response = await fetch("/api/summary-test");
        if (!response.ok) throw new Error("Could not load summary. Please try again.");
        const summary = await response.json();
        if (typeof summary.answered_both !== "number") {
            throw new Error("Summary data is outdated. Restart the Python server and refresh this page.");
        }
        for (const cell of document.querySelectorAll("[data-summary]")) {
            cell.textContent = summary[cell.dataset.summary];
        }
        drawWordingPie(summary);
        document.getElementById("summaryContent").classList.remove("hidden");
        message.textContent = "";
    } catch (error) {
        message.textContent = error.message;
    }
}


// Draw the female/male split using participants who answered both as the total.
function drawWordingPie(summary) {
    const total = summary.answered_both;
    const female = total ? summary.females_both / total * 100 : 0;
    const male = total ? summary.males_both / total * 100 : 0;
    const pie = document.getElementById("wordingPie");
    pie.style.background = total
        ? `conic-gradient(#94608e 0% ${female}%, #427d9d ${female}% ${female + male}%, #dce2e7 ${female + male}% 100%)`
        : "#dce2e7";
    pie.setAttribute("aria-label", total
        ? `Among ${total} participants who answered both: ${summary.females_both} female wording, ${summary.males_both} male wording. Any gray portion represents unrecorded wording.`
        : "No participants answered both questionnaires.");
    document.getElementById("femalePercent").textContent = `(${female.toFixed(1)}%)`;
    document.getElementById("malePercent").textContent = `(${male.toFixed(1)}%)`;
    document.getElementById("wordingMessage").textContent = total
        ? `Total answered both: ${total}. Any gray portion represents unrecorded wording.`
        : "No participants answered both questionnaires.";
}

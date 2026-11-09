let participantsTableData = null;
let participantsTableView = null;
let participantsTableSaving = false;
let participantsTableSort = null;
const selectedParticipantColumns = new Set();


document.addEventListener(
    "DOMContentLoaded",
    function () {

        const participantsLink =
            document.getElementById(
                "participantsLink"
            );

        participantsLink.addEventListener(
            "click",
            function (event) {
                event.preventDefault();
                loadParticipantsTable();
            }
        );

        setupParticipantsFilters();

        document.getElementById("selectAllScores").addEventListener("change", event => {
            setParticipantColumnsSelected(getScoreColumnKeys(), event.target.checked);
        });

        document.getElementById("showSelectedParticipantsColumns").addEventListener(
            "click",
            showSelectedParticipantsColumns
        );

        document.getElementById("showAnswerLabels").addEventListener(
            "change",
            applyParticipantsFilters
        );

        document.getElementById("saveParticipantsTable").addEventListener(
            "click",
            saveParticipantsTable
        );
    }
);


async function fetchParticipantsTable() {

    const response = await fetch(
        "/api/participants-table"
    );

    if (!response.ok) {
        throw new Error(
            "Could not load participants table"
        );
    }

    return await response.json();
}


async function loadParticipantsTable() {

    document.getElementById("summarySection").classList.add("hidden");
    participantsTableSort = null;
    participantsTableData = null;
    participantsTableView = null;
    updateSaveParticipantsButton();

    const section = document.getElementById(
        "participantsTableSection"
    );
    const message = document.getElementById(
        "participantsTableMessage"
    );
    const table = document.getElementById(
        "participantsTable"
    );

    section.classList.remove(
        "hidden"
    );
    table.classList.add(
        "hidden"
    );
    message.textContent =
        "Loading participants table...";

    setActiveSidebarLink(
        "participantsLink"
    );

    try {

        const tableData =
            await fetchParticipantsTable();

        const firstTests = ["demog-health", "trauma-checklist", "PCL"];
        tableData.groups = [
            ...firstTests.flatMap(test => tableData.groups.filter(group => group.test === test)),
            ...tableData.groups.filter(group => !firstTests.includes(group.test)),
        ];

        participantsTableData = tableData;

        populateColumnFilter(
            tableData.fixed_columns,
            tableData.groups
        );

        applyParticipantsFilters();

        table.classList.remove(
            "hidden"
        );

    } catch (error) {

        participantsTableData = null;
        participantsTableView = null;
        updateSaveParticipantsButton();
        console.error(error);
        message.textContent =
            error.message;
    }
}


function setupParticipantsFilters() {

    const filterIds = [
        "participantSubjectFilter",
        "answeredQuestionnaire1Filter",
        "answeredQuestionnaire2Filter",
        "answeredBothFilter",
        "columnFilter",
        "conditionFilter",
        "filterValue",
        "testGroupFilter",
        "hiddenColumnsFilter",
        "hideEmptyColumnsFilter",
    ];

    for (const filterId of filterIds) {

        const element = document.getElementById(
            filterId
        );

        if (!element) {
            continue;
        }

        element.addEventListener(
            "input",
            applyParticipantsFilters
        );
        element.addEventListener(
            "change",
            applyParticipantsFilters
        );
    }

    const clearButton = document.getElementById(
        "clearParticipantsFilters"
    );

    if (clearButton) {
        clearButton.addEventListener(
            "click",
            clearParticipantsFilters
        );
    }

    const showAllColumnsButton = document.getElementById(
        "showAllParticipantsColumns"
    );

    if (showAllColumnsButton) {
        showAllColumnsButton.addEventListener(
            "click",
            showAllParticipantsColumns
        );
    }
}


function populateColumnFilter(fixedColumns, groups) {

    const columnFilter = document.getElementById(
        "columnFilter"
    );

    if (!columnFilter) {
        return;
    }

    const currentValue = columnFilter.value;
    columnFilter.innerHTML =
        "<option value=\"\">Select column</option>";

    const columns = [
        {
            key: "subject_id",
            label: "participant/subject_id",
        },
        ...(fixedColumns || []),
    ];

    for (const group of groups || []) {
        for (const column of group.columns) {
            columns.push(
                {
                    key: column.key,
                    label: `${group.test} - ${column.label}`,
                }
            );
        }
    }

    for (const column of columns) {
        const option = document.createElement(
            "option"
        );
        option.value = column.key;
        option.textContent = column.label;
        columnFilter.appendChild(
            option
        );
    }

    columnFilter.value = currentValue;

    populateDisplayColumnControls(
        fixedColumns,
        groups,
        columns
    );
}


function getTestFilterName(test) {
    return ["trauma-checklist", "PCL"].includes(test) ? "trauma-checklist + PCL" : test;
}


function populateDisplayColumnControls(fixedColumns, groups, columns) {

    const testGroupFilter = document.getElementById(
        "testGroupFilter"
    );
    const hiddenColumnsFilter = document.getElementById(
        "hiddenColumnsFilter"
    );

    if (testGroupFilter) {
        const currentGroup = testGroupFilter.value;
        testGroupFilter.innerHTML =
            "<option value=\"\">All tests</option>";

        const testNames = new Set((groups || []).map(group => getTestFilterName(group.test)));
        for (const test of testNames) {
            const option = document.createElement(
                "option"
            );
            option.value = test;
            option.textContent = test;
            testGroupFilter.appendChild(
                option
            );
        }

        testGroupFilter.value = currentGroup;
    }

    if (hiddenColumnsFilter) {
        const hiddenValues = new Set(
            Array.from(
                hiddenColumnsFilter.querySelectorAll(
                    "input[type='checkbox']:not(:checked)"
                )
            ).map(
                checkbox => checkbox.value
            )
        );

        hiddenColumnsFilter.innerHTML = "";

        const search = document.createElement("input");
        search.type = "search";
        search.placeholder = "Search columns...";
        search.setAttribute("aria-label", "Search columns");
        search.className = "column-picker-search";
        search.addEventListener("input", event => {
            event.stopPropagation();
            const query = search.value.trim().toLowerCase();
            for (const label of hiddenColumnsFilter.querySelectorAll(".column-hide-option")) {
                label.hidden = !label.textContent.toLowerCase().includes(query);
            }
        });
        hiddenColumnsFilter.appendChild(search);

        const help = document.createElement("p");
        help.textContent = "Check columns to show them. Subject ID always stays visible.";
        hiddenColumnsFilter.appendChild(help);

        for (const group of groups || []) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "secondary-button";
            button.textContent = `Hide questions: ${group.test}`;

            button.addEventListener("click", () => {
                const questionKeys = new Set(
                    group.columns
                        .filter(column => column.key.startsWith("canonical_"))
                        .map(column => column.key)
                );

                for (const checkbox of hiddenColumnsFilter.querySelectorAll(
                    "input[type='checkbox']"
                )) {
                    if (questionKeys.has(checkbox.value)) {
                        checkbox.checked = false;
                    }
                }

                applyParticipantsFilters();
            });

            hiddenColumnsFilter.appendChild(button);
        }

        for (const column of columns) {
            const label = document.createElement(
                "label"
            );
            label.classList.add(
                "column-hide-option"
            );

            const checkbox = document.createElement(
                "input"
            );
            checkbox.type = "checkbox";
            checkbox.value = column.key;
            checkbox.checked = !hiddenValues.has(column.key);
            checkbox.addEventListener(
                "change",
                applyParticipantsFilters
            );

            const text = document.createElement(
                "span"
            );
            text.textContent = column.label;

            label.appendChild(checkbox);
            label.appendChild(text);
            hiddenColumnsFilter.appendChild(
                label
            );
        }

        updateHiddenColumnsSummary();
    }
}


function getDisplayedParticipantsRows(rows, groups) {
    if (!document.getElementById("showAnswerLabels").checked) {
        return rows;
    }

    return rows.map(row => {
        const displayedRow = { ...row };
        const labels = participantsTableData.answer_labels?.[String(row.subject_id)];
        for (const group of groups) {
            for (const column of group.columns) {
                const label = labels?.[column.key];
                if (typeof row[column.key] === "number" &&
                    typeof label === "string" && label.trim()) {
                    displayedRow[column.key] = label;
                }
            }
        }
        return displayedRow;
    });
}


function sortParticipantsRows(rows, groups) {
    if (!participantsTableSort) {
        return rows;
    }

    const { key, direction } = participantsTableSort;
    if (!groups.some(group => group.columns.some(column => column.key === key))) {
        participantsTableSort = null;
        return rows;
    }

    return [...rows].sort((left, right) => {
        const leftScore = left[key];
        const rightScore = right[key];
        const leftMissing = !Number.isFinite(leftScore);
        const rightMissing = !Number.isFinite(rightScore);

        if (leftMissing || rightMissing) {
            return Number(leftMissing) - Number(rightMissing);
        }

        return direction === "descending"
            ? rightScore - leftScore
            : leftScore - rightScore;
    });
}


function applyParticipantsFilters() {

    if (!participantsTableData) {
        return;
    }

    updateHiddenColumnsSummary();

    const filteredRows = participantsTableData.rows.filter(
        rowMatchesParticipantsFilters
    );

    const fixedColumns = getVisibleFixedColumns(
        participantsTableData.fixed_columns,
        filteredRows
    );
    const groups = getVisibleGroups(
        participantsTableData.groups,
        filteredRows
    );

    const sortedRows = sortParticipantsRows(filteredRows, groups);
    const displayedRows = getDisplayedParticipantsRows(sortedRows, groups);
    drawParticipantsTable(fixedColumns, groups, displayedRows);
    updateSelectedColumnsButton();

    participantsTableView = {
        fixed_columns: fixedColumns,
        groups: groups,
        rows: displayedRows,
        filter_description: getParticipantsFilterDescription(),
    };
    updateSaveParticipantsButton();

    updateParticipantsTableMessage(
        filteredRows.length,
        participantsTableData.rows.length
    );
}


function updateSaveParticipantsButton() {
    const button = document.getElementById("saveParticipantsTable");

    if (button) {
        button.disabled = participantsTableSaving || !participantsTableView ||
            participantsTableView.rows.length === 0;
        button.textContent = participantsTableSaving ? "Saving..." : "Save table (.xlsx)";
    }
}


function getParticipantsSaveDate(now = new Date()) {
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
}


async function saveParticipantsTable() {
    if (participantsTableSaving || !participantsTableView ||
        participantsTableView.rows.length === 0) {
        return;
    }

    const errorMessage = document.getElementById("participantsExportMessage");
    errorMessage.textContent = "";
    participantsTableSaving = true;
    updateSaveParticipantsButton();

    try {
        const saveDate = getParticipantsSaveDate();
        const filename = `participants_table_${saveDate}.xlsx`;
        const body = JSON.stringify({
            ...participantsTableView,
            save_date: saveDate,
        });
        let fileHandle = null;

        // Open the dialog directly from the click, before the network request.
        if (typeof window.showSaveFilePicker === "function") {
            try {
                fileHandle = await window.showSaveFilePicker({
                    suggestedName: filename,
                    types: [{
                        description: "Excel workbook",
                        accept: {
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
                        },
                    }],
                });
            } catch (error) {
                if (error.name === "AbortError") {
                    return;
                }
                throw error;
            }
        }

        const response = await fetch("/api/participants-table/export", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: body,
        });

        if (!response.ok) {
            let message = "Could not save the table. Please try again.";
            const details = await response.json().catch(() => null);
            if (typeof details?.detail === "string") {
                message = details.detail;
            }
            throw new Error(message);
        }

        const blob = await response.blob();
        if (fileHandle) {
            const writable = await fileHandle.createWritable();
            try {
                await writable.write(blob);
                await writable.close();
            } catch (error) {
                await writable.abort().catch(() => {});
                throw error;
            }
            return;
        }

        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        try {
            link.click();
        } finally {
            link.remove();
            // Give the browser time to start the download before releasing the URL.
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        }
    } catch (error) {
        errorMessage.textContent = `Save failed: ${error.message}`;
    } finally {
        participantsTableSaving = false;
        updateSaveParticipantsButton();
    }
}


function getParticipantsFilterDescription() {
    const filters = [];
    const rowFilters = [
        ["participantSubjectFilter", "Subject ID contains"],
        ["answeredQuestionnaire1Filter", "Questionnaire 1"],
        ["answeredQuestionnaire2Filter", "Questionnaire 2"],
        ["answeredBothFilter", "Both questionnaires"],
    ];

    for (const [id, label] of rowFilters) {
        const value = getFilterValue(id);
        if (value) {
            filters.push(`${label}: ${value}`);
        }
    }

    const columnKey = getFilterValue("columnFilter");
    const condition = getFilterValue("conditionFilter") || "contains";
    const value = getFilterValue("filterValue");
    const needsNoValue = condition === "empty" || condition === "not_empty";

    if (columnKey && (value || needsNoValue)) {
        const columnSelect = document.getElementById("columnFilter");
        const conditionSelect = document.getElementById("conditionFilter");
        const columnLabel = columnSelect.selectedOptions[0].textContent;
        const conditionLabel = conditionSelect.selectedOptions[0].textContent;
        filters.push(
            `${columnLabel}: ${conditionLabel}${needsNoValue ? "" : ` ${value}`}`
        );
    }

    const test = getFilterValue("testGroupFilter");
    if (test) {
        filters.push(`Show test: ${test}`);
    }

    const hiddenColumns = document.getElementById("hiddenColumnsFilter");
    if (hiddenColumns) {
        const labels = Array.from(
            hiddenColumns.querySelectorAll("input[type='checkbox']:not(:checked)")
        ).map(checkbox => checkbox.parentElement.textContent.trim());

        if (labels.length) {
            filters.push(`Hidden columns: ${labels.join(", ")}`);
        }
    }

    if (shouldHideEmptyColumns()) {
        filters.push("Hide empty columns");
    }

    return filters.length ? filters.join("; ") : "None";
}


function getHiddenColumnKeys() {

    const hiddenColumnsFilter = document.getElementById(
        "hiddenColumnsFilter"
    );

    if (!hiddenColumnsFilter) {
        return new Set();
    }

    return new Set(
        Array.from(
            hiddenColumnsFilter.querySelectorAll(
                "input[type='checkbox']:not(:checked)"
            )
        ).map(
            checkbox => checkbox.value
        )
    );
}


function shouldHideEmptyColumns() {

    const checkbox = document.getElementById(
        "hideEmptyColumnsFilter"
    );

    return Boolean(checkbox && checkbox.checked);
}


function isColumnEmpty(columnKey, rows) {

    return rows.every(
        row => normalizeFilterText(row[columnKey]) === ""
    );
}


function getVisibleFixedColumns(fixedColumns, rows) {

    const hiddenColumnKeys = getHiddenColumnKeys();
    const hideEmpty = shouldHideEmptyColumns();

    return (fixedColumns || []).filter(
        column => {
            if (hiddenColumnKeys.has(column.key)) {
                return false;
            }

            if (hideEmpty && isColumnEmpty(column.key, rows)) {
                return false;
            }

            return true;
        }
    );
}


function getVisibleGroups(groups, rows) {

    const selectedGroup = getFilterValue(
        "testGroupFilter"
    );
    const hiddenColumnKeys = getHiddenColumnKeys();
    const hideEmpty = shouldHideEmptyColumns();
    const visibleGroups = [];

    for (const group of groups || []) {
        if (selectedGroup && getTestFilterName(group.test) !== selectedGroup) {
            continue;
        }

        const columns = group.columns.filter(
            column => {
                if (hiddenColumnKeys.has(column.key)) {
                    return false;
                }

                if (hideEmpty && isColumnEmpty(column.key, rows)) {
                    return false;
                }

                return true;
            }
        );

        if (columns.length === 0) {
            continue;
        }

        visibleGroups.push(
            {
                ...group,
                columns: columns,
            }
        );
    }

    return visibleGroups;
}


function rowMatchesParticipantsFilters(rowData) {

    const subjectFilter = getFilterValue(
        "participantSubjectFilter"
    );

    if (
        subjectFilter &&
        !normalizeFilterText(rowData.subject_id).includes(
            normalizeFilterText(subjectFilter)
        )
    ) {
        return false;
    }

    if (!matchesSelectFilter(
        rowData,
        "answered_questionnaire_1",
        "answeredQuestionnaire1Filter"
    )) {
        return false;
    }

    if (!matchesSelectFilter(
        rowData,
        "answered_questionnaire_2",
        "answeredQuestionnaire2Filter"
    )) {
        return false;
    }

    if (!matchesSelectFilter(
        rowData,
        "answered_both_questionnaires",
        "answeredBothFilter"
    )) {
        return false;
    }

    const columnKey = getFilterValue(
        "columnFilter"
    );

    if (!columnKey) {
        return true;
    }

    return matchesColumnCondition(
        rowData[columnKey],
        getFilterValue("conditionFilter") || "contains",
        getFilterValue("filterValue")
    );
}


function matchesSelectFilter(rowData, rowKey, filterId) {

    const selectedValue = getFilterValue(filterId);

    if (!selectedValue) {
        return true;
    }

    return String(rowData[rowKey] ?? "") === selectedValue;
}


function matchesColumnCondition(value, condition, filterValue) {

    const cellText = normalizeFilterText(value);
    const wantedText = normalizeFilterText(filterValue);

    if (condition === "empty") {
        return cellText === "";
    }

    if (condition === "not_empty") {
        return cellText !== "";
    }

    if (!wantedText) {
        return true;
    }

    if (condition === "equals") {
        return cellText === wantedText;
    }

    if (condition === "not_equals") {
        return cellText !== wantedText;
    }

    if (condition === "not_contains") {
        return !cellText.includes(wantedText);
    }

    if (condition === "greater_than") {
        return Number(cellText) > Number(wantedText);
    }

    if (condition === "less_than") {
        return Number(cellText) < Number(wantedText);
    }

    return cellText.includes(wantedText);
}


function getFilterValue(filterId) {

    const element = document.getElementById(
        filterId
    );

    if (!element) {
        return "";
    }

    return element.value.trim();
}


function normalizeFilterText(value) {

    if (value === null || value === undefined) {
        return "";
    }

    return String(value).trim().toLowerCase();
}


function updateParticipantsTableMessage(filteredCount, totalCount) {

    const message = document.getElementById(
        "participantsTableMessage"
    );

    if (!message) {
        return;
    }

    if (totalCount === 0) {
        message.textContent =
            "No participants were found.";
        return;
    }

    if (filteredCount === totalCount) {
        message.textContent = "";
        return;
    }

    message.textContent =
        `Showing ${filteredCount} of ${totalCount} participants.`;
}


function clearParticipantsFilters() {

    const filterIds = [
        "participantSubjectFilter",
        "answeredQuestionnaire1Filter",
        "answeredQuestionnaire2Filter",
        "answeredBothFilter",
        "columnFilter",
        "filterValue",
    ];

    for (const filterId of filterIds) {
        const element = document.getElementById(
            filterId
        );

        if (element) {
            element.value = "";
        }
    }

    const conditionFilter = document.getElementById(
        "conditionFilter"
    );

    if (conditionFilter) {
        conditionFilter.value = "contains";
    }

    applyParticipantsFilters();
}


function updateSelectedColumnsButton() {
    document.getElementById("showSelectedParticipantsColumns").disabled =
        selectedParticipantColumns.size === 0;

    for (const checkbox of document.querySelectorAll(".column-selection-checkbox")) {
        updateColumnSelectionState(checkbox, checkbox.columnKeys);
    }
    updateColumnSelectionState(document.getElementById("selectAllScores"), getScoreColumnKeys());
}


function getScoreColumnKeys() {
    return (participantsTableData?.groups || []).flatMap(group =>
        group.columns.filter(column => column.key.startsWith("score_")).map(column => column.key)
    );
}


function updateColumnSelectionState(checkbox, keys) {
    const selectedCount = keys.filter(key => selectedParticipantColumns.has(key)).length;
    checkbox.checked = keys.length > 0 && selectedCount === keys.length;
    checkbox.indeterminate = selectedCount > 0 && selectedCount < keys.length;
    checkbox.disabled = keys.length === 0;
}


function setParticipantColumnsSelected(keys, selected) {
    for (const key of keys) {
        if (selected) {
            selectedParticipantColumns.add(key);
        } else {
            selectedParticipantColumns.delete(key);
        }
    }
    updateSelectedColumnsButton();
}


function appendColumnSelectionCheckbox(header, column, label, columns = [column]) {
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "column-selection-checkbox";
    checkbox.columnKeys = columns.map(column => column.key);
    updateColumnSelectionState(checkbox, checkbox.columnKeys);
    checkbox.setAttribute("aria-label", `Select column: ${label}`);
    checkbox.addEventListener("change", () => {
        setParticipantColumnsSelected(checkbox.columnKeys, checkbox.checked);
    });
    header.prepend(checkbox);
}


function showSelectedParticipantsColumns() {
    if (selectedParticipantColumns.size === 0) return;

    for (const checkbox of document.querySelectorAll("#hiddenColumnsFilter input[type='checkbox']")) {
        checkbox.checked = selectedParticipantColumns.has(checkbox.value);
    }
    applyParticipantsFilters();
}


function showAllParticipantsColumns() {

    selectedParticipantColumns.clear();
    updateSelectedColumnsButton();

    const testGroupFilter = document.getElementById(
        "testGroupFilter"
    );
    const hiddenColumnsFilter = document.getElementById(
        "hiddenColumnsFilter"
    );
    const hideEmptyColumnsFilter = document.getElementById(
        "hideEmptyColumnsFilter"
    );

    if (testGroupFilter) {
        testGroupFilter.value = "";
    }

    if (hiddenColumnsFilter) {
        for (const checkbox of hiddenColumnsFilter.querySelectorAll(
            "input[type='checkbox']"
        )) {
            checkbox.checked = true;
        }
    }

    if (hideEmptyColumnsFilter) {
        hideEmptyColumnsFilter.checked = false;
    }

    applyParticipantsFilters();
}


function updateHiddenColumnsSummary() {

    const summary = document.getElementById(
        "hiddenColumnsSummary"
    );
    const hiddenColumnsFilter = document.getElementById(
        "hiddenColumnsFilter"
    );

    if (!summary || !hiddenColumnsFilter) {
        return;
    }

    const hiddenCount = hiddenColumnsFilter.querySelectorAll(
        "input[type='checkbox']:not(:checked)"
    ).length;

    if (hiddenCount === 0) {
        summary.textContent = "All columns selected";
    } else {
        const total = hiddenColumnsFilter.querySelectorAll("input[type='checkbox']").length;
        summary.textContent = `${total - hiddenCount} of ${total} columns selected`;
    }
}


function getTestColorClass(groupIndex) {
    return `test-color-${(groupIndex % 8) + 1}`;
}


function getQuestionTooltip(column) {
    if (column.tooltip) {
        return column.tooltip;
    }

    if (column.question_number) {
        return `Question ${column.question_number}`;
    }

    return column.label;
}


function appendQuestionHeaderText(header, column) {
    if (column.parent_question) {
        const parentText = document.createElement("div");
        parentText.classList.add("question-parent-text");
        parentText.textContent = column.parent_question;
        header.appendChild(parentText);
    }

    const questionText = document.createElement("div");
    questionText.classList.add("question-text");
    questionText.textContent = column.question || column.label;
    header.appendChild(questionText);
}


function getDemographicChart(column) {
    return {
        DEMOG_HEALTH_04: { label: "Age (years)", unit: "years" },
        DEMOG_HEALTH_09: { label: "Height (cm)", unit: "cm" },
        DEMOG_HEALTH_10: { label: "Weight (kg)", unit: "kg" },
    }[column.canonical_code];
}


function getDemographicChartSlices(column, data, population) {
    const rows = data.rows.filter(row => row.answered_both_questionnaires === "Yes");
    const unit = getDemographicChart(column).unit;
    const binStarts = new Set();
    for (const row of population.rows) {
        const value = row[column.key];
        if (row.answered_both_questionnaires === "Yes" && Number.isFinite(value)) {
            binStarts.add(Math.floor(value / 5) * 5);
        }
    }
    const counts = new Map([...binStarts].sort((a, b) => a - b).map(start => [start, 0]));
    let missing = 0;
    for (const row of rows) {
        const value = row[column.key];
        if (Number.isFinite(value)) {
            const start = Math.floor(value / 5) * 5;
            counts.set(start, (counts.get(start) || 0) + 1);
        } else {
            missing += 1;
        }
    }
    const slices = [...counts].map(([start, count]) => ({
        label: `${start}–<${start + 5} ${unit}`, count,
    }));
    if (missing) slices.push({ label: "Missing value", count: missing });
    return { total: rows.length, slices };
}


function getScoreChartSlices(column, data) {
    if (getDemographicChart(column)) {
        return getDemographicChartSlices(column, data, participantsTableData);
    }
    const rows = data.rows.filter(row => row.answered_both_questionnaires === "Yes");
    const categories = column.interpretation_ranges || [];
    const missingLabel = column.missing_score_label || "Missing score";
    const counts = new Map();
    for (const category of categories) {
        if (category.label) counts.set(category.label, 0);
    }
    if (column.missing_score_label === "No PCL answer") counts.set(missingLabel, 0);
    for (const row of rows) {
        const score = row[column.key];
        let label = missingLabel;
        if (typeof score === "number" && Number.isFinite(score)) {
            label = categories.length
                ? data.score_interpretations?.[String(row.subject_id)]?.[column.key] || "Unclassified"
                : String(score);
        }
        counts.set(label, (counts.get(label) || 0) + 1);
    }
    const labels = categories.length
        ? [...new Set(categories.map(range => range.label).filter(Boolean))]
        : [...counts.keys()].filter(label => label !== missingLabel)
            .sort((left, right) => Number(left) - Number(right));
    for (const label of counts.keys()) {
        if (!labels.includes(label)) labels.push(label);
    }
    return {
        total: rows.length,
        slices: labels.filter(label => counts.has(label))
            .map(label => ({ label, count: counts.get(label) })),
    };
}


function showScoreChart(column, testName, opener) {
    const dialog = document.getElementById("scoreChartDialog");
    const demographic = getDemographicChart(column);
    const { total } = getScoreChartSlices(column, participantsTableData);
    const ranges = column.interpretation_ranges || [];
    document.getElementById("scoreChartTitle").textContent = demographic
        ? demographic.label : `${testName} — ${column.label}`;
    document.getElementById("scoreChartDescription").textContent =
        demographic ? "Distribution of reported values among participants who answered both questionnaires."
            : column.description?.trim() || "No subscale description is available";
    const method = column.scoring_method === "average" ? "Average" : "Sum";
    const limits = column.min_score != null && column.max_score != null
        ? ` Possible scores: ${column.min_score}–${column.max_score}.` : "";
    document.getElementById("scoreChartMethod").textContent = demographic
        ? `Unit: ${demographic.unit}. Interval width: 5 ${demographic.unit}; lower bound included, upper bound excluded. Missing or nonnumeric values are included in totals as Missing value.`
        : `Calculation: ${method}.${limits}`;
    const rangeList = document.getElementById("scoreChartRanges");
    rangeList.replaceChildren();
    for (const range of ranges) {
        const item = document.createElement("li");
        item.dir = "auto";
        item.textContent = `${range.label || "Unlabeled category"}: ${range.min ?? "?"}–${range.max ?? "?"} (inclusive)`;
        rangeList.appendChild(item);
    }
    document.getElementById("scoreChartPopulation").textContent = total
        ? `${total} participants who answered both questionnaires; table filters do not affect this chart. `
            + (demographic ? "Grouped frequency bars show participant counts and percentages."
                : ranges.length ? "Pie chart grouped by cutoff / threshold categories."
                : "Bar plot by exact score value. Bar length shows the number of participants; no cutoff / threshold categories are defined.")
        : "No participants answered both questionnaires.";
    const groups = document.getElementById("scoreChartGroups");
    groups.replaceChildren();
    for (const [title, wording] of [["All participants", null], ["Female wording", "female"], ["Male wording", "male"]]) {
        const data = {
            ...participantsTableData,
            rows: participantsTableData.rows.filter(row => !wording || row.wording_form === wording),
        };
        drawScoreChartGroup(groups, column, data, title);
    }
    const ungrouped = participantsTableData.rows.filter(row =>
        row.answered_both_questionnaires === "Yes"
        && !["female", "male"].includes(row.wording_form)
    ).length;
    if (ungrouped) {
        document.getElementById("scoreChartPopulation").textContent +=
            ` ${ungrouped} participants have unrecorded or mixed wording and appear only in the overall chart.`;
    }
    dialog.addEventListener("close", () => {
        if (opener.isConnected) opener.focus();
    }, { once: true });
    dialog.showModal();
}


function drawScoreChartGroup(container, column, data, title) {
    const { total, slices } = getScoreChartSlices(column, data);
    const ranges = column.interpretation_ranges || [];
    const missingLabel = getDemographicChart(column) ? "Missing value"
        : column.missing_score_label || "Missing score";
    const section = document.createElement("section");
    const heading = document.createElement("h3");
    heading.textContent = `${title} (${total})`;
    const pie = document.createElement("div");
    pie.className = "score-chart-pie";
    pie.setAttribute("role", "img");
    const legend = document.createElement("ul");
    legend.className = "score-chart-legend";
    section.append(heading, pie, legend);
    container.appendChild(section);
    if (!total) {
        pie.hidden = true;
        const message = document.createElement("p");
        message.textContent = "No participants in this group answered both questionnaires.";
        section.appendChild(message);
        return;
    }
    legend.classList.toggle("score-chart-bars", !ranges.length);
    const maxCount = Math.max(1, ...slices.map(slice => slice.count));
    const stops = [];
    let cumulative = 0;
    for (const [index, slice] of slices.entries()) {
        const percent = slice.count / total * 100;
        const color = slice.label === missingLabel ? "#c8cdd3"
            : slice.label === "Unclassified" ? "#737b85"
                : `hsl(${index * 137.508 % 360} 55% 46%)`;
        stops.push(`${color} ${cumulative}% ${cumulative + percent}%`);
        cumulative += percent;
        const item = document.createElement("li");
        const key = document.createElement("span");
        key.className = "score-chart-key";
        key.style.background = color;
        key.setAttribute("aria-hidden", "true");
        const text = document.createElement("span");
        text.dir = "auto";
        text.textContent = `${slice.label}: ${slice.count} (${percent.toFixed(1)}%)`;
        if (ranges.length) {
            item.append(key, text);
        } else {
            const track = document.createElement("span");
            track.className = "score-chart-bar-track";
            track.setAttribute("aria-hidden", "true");
            const bar = document.createElement("span");
            bar.className = "score-chart-bar";
            bar.style.width = `${slice.count / maxCount * 100}%`;
            bar.style.background = slice.label === missingLabel ? "#c8cdd3" : "#427d9d";
            track.appendChild(bar);
            item.append(text, track);
        }
        legend.appendChild(item);
    }
    pie.hidden = !total || !ranges.length;
    pie.style.background = total && ranges.length ? `conic-gradient(${stops.join(", ")})` : "#c8cdd3";
    pie.setAttribute("aria-label", total
        ? `${title} — ${column.label}. ${slices.map(slice => `${slice.label}: ${slice.count} (${(slice.count / total * 100).toFixed(1)}%)`).join("; ")}`
        : "No participants answered both questionnaires.");
}


function appendScoreChartButton(header, column, testName) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary-button score-chart-button";
    button.textContent = "View chart";
    button.setAttribute("aria-label", getDemographicChart(column)
        ? `View chart for ${getDemographicChart(column).label}`
        : `View chart for ${testName} — ${column.label}`);
    button.addEventListener("click", () => showScoreChart(column, testName, button));
    header.querySelector(".question-text").appendChild(button);
}


function appendScoreSortButton(header, column, testName) {
    const direction = participantsTableSort?.key === column.key
        ? participantsTableSort.direction
        : null;
    const nextDirection = direction === "descending" ? "ascending" : "descending";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "score-sort-button";
    const arrowPath = direction === "descending"
        ? "M12 4v16m-6-6 6 6 6-6"
        : direction === "ascending"
            ? "M12 20V4m-6 6 6-6 6 6"
            : "M8 20V4m-4 4 4-4 4 4M16 4v16m-4-4 4 4 4-4";
    button.innerHTML = `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false"><path d="${arrowPath}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
    button.setAttribute(
        "aria-label",
        `Sort ${testName} - ${column.label}: ${nextDirection === "descending" ? "highest" : "lowest"} first`
    );
    button.title = button.getAttribute("aria-label");
    if (direction) {
        header.setAttribute("aria-sort", direction);
    }
    button.addEventListener("click", () => {
        participantsTableSort = { key: column.key, direction: nextDirection };
        applyParticipantsFilters();
        const updatedButton = document.getElementById("participantsTableHead")
            .querySelector("[aria-sort] .score-sort-button");
        updatedButton?.focus();
    });
    header.querySelector(".question-text").appendChild(button);
}


/*
Input: cell is the table cell, rowData is the participant's row,
and column is the column definition.
Output: appends the score interpretation alongside the existing number.
*/
function appendScoreInterpretation(cell, rowData, column) {
    if (!column.key.startsWith("score_")) {
        return;
    }

    const interpretation = participantsTableData
        ?.score_interpretations
        ?.[String(rowData.subject_id)]
        ?.[column.key];

    if (!interpretation) {
        return;
    }

    const label = document.createElement("div");
    label.className = "score-interpretation";
    label.dir = "auto";
    label.textContent = interpretation;
    cell.title = `${rowData[column.key] ?? ""} — ${interpretation}`;
    cell.appendChild(label);
}


function drawParticipantsTable(fixedColumns, groups, rows) {

    fixedColumns = fixedColumns || [];

    const tableHead = document.getElementById(
        "participantsTableHead"
    );
    const tableBody = document.getElementById(
        "participantsTableBody"
    );

    tableHead.innerHTML = "";
    tableBody.innerHTML = "";

    const groupHeaderRow =
        document.createElement("tr");

    const participantHeader =
        document.createElement("th");
    participantHeader.textContent =
        "participant/subject_id";
    participantHeader.rowSpan = 2;
    participantHeader.classList.add(
        "sticky-column"
    );
    groupHeaderRow.appendChild(
        participantHeader
    );

    for (const column of fixedColumns) {

        const fixedHeader =
            document.createElement("th");
        fixedHeader.textContent =
            column.label;
        fixedHeader.title =
            column.tooltip || column.label;
        appendColumnSelectionCheckbox(fixedHeader, column, column.label);
        fixedHeader.rowSpan = 2;
        fixedHeader.classList.add(
            "fixed-column-header"
        );
        groupHeaderRow.appendChild(
            fixedHeader
        );
    }

    for (const [groupIndex, group] of groups.entries()) {

        const groupHeader =
            document.createElement("th");
        groupHeader.textContent =
            group.test;
        const testColumns = participantsTableData.groups
            .filter(testGroup => testGroup.test === group.test)
            .flatMap(testGroup => testGroup.columns);
        appendColumnSelectionCheckbox(groupHeader, null, `All columns in ${group.test}`, testColumns);
        groupHeader.colSpan =
            group.columns.length;
        groupHeader.classList.add(
            "test-group-header",
            getTestColorClass(groupIndex)
        );
        groupHeaderRow.appendChild(
            groupHeader
        );
    }

    tableHead.appendChild(
        groupHeaderRow
    );

    const codeHeaderRow =
        document.createElement("tr");
    const flatColumns = [];

    for (const [groupIndex, group] of groups.entries()) {
        const colorClass = getTestColorClass(groupIndex);

        for (const column of group.columns) {

            flatColumns.push(
                {
                    ...column,
                    colorClass: colorClass,
                }
            );

            const codeHeader =
                document.createElement("th");
            const questionTooltip = getQuestionTooltip(column);

            appendQuestionHeaderText(
                codeHeader,
                column
            );
            if ((column.question || column.label || "").includes("איך נוח לך שהשאלון ינוסח")) {
                appendScoreSortButton(codeHeader, column, group.test);
            }
            if (column.key.startsWith("score_")) {
                codeHeader.classList.add("score-column-header");
                appendScoreSortButton(codeHeader, column, group.test);
                appendScoreChartButton(codeHeader, column, group.test);
            } else if (getDemographicChart(column)) {
                appendScoreChartButton(codeHeader, column, group.test);
            }
            codeHeader.title =
                questionTooltip;
            appendColumnSelectionCheckbox(codeHeader, column, `${group.test} - ${column.label}`);

            codeHeader.classList.add(
                "canonical-code-header",
                colorClass
            );
            codeHeaderRow.appendChild(
                codeHeader
            );
        }
    }

    tableHead.appendChild(
        codeHeaderRow
    );

    for (const rowData of rows) {

        const row =
            document.createElement("tr");
        const participantCell =
            document.createElement("td");
        participantCell.textContent =
            rowData.subject_id ?? "";
        participantCell.classList.add(
            "sticky-column"
        );
        row.appendChild(
            participantCell
        );

        for (const column of fixedColumns) {

            const cell =
                document.createElement("td");
            cell.textContent =
                rowData[column.key] ?? "";
            cell.title = cell.textContent;
            row.appendChild(
                cell
            );
        }

        for (const column of flatColumns) {

            const cell =
                document.createElement("td");
            cell.textContent =
                rowData[column.key] ?? "";
            cell.title = cell.textContent;
            appendScoreInterpretation(cell, rowData, column);
            cell.classList.add(
                "participant-answer-cell",
                column.colorClass
            );
            row.appendChild(
                cell
            );
        }

        tableBody.appendChild(
            row
        );
    }
}


function setActiveSidebarLink(activeLinkId) {

    const sidebarLinks =
        document.querySelectorAll(
            ".sidebar-link"
        );

    for (const link of sidebarLinks) {
        link.classList.remove(
            "active"
        );
    }

    document.getElementById(
        activeLinkId
    ).classList.add(
        "active"
    );
}

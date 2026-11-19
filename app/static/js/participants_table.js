let participantsTableData = null;
let participantsTableView = null;
let participantsTableSaving = false;
let participantsTableSort = null;
const participantsColumnWidths = new Map();
const participantsGroupHeaderObserver = new ResizeObserver(([entry]) => {
    entry.target.closest("table").style.setProperty(
        "--participants-group-header-height",
        `${entry.target.getBoundingClientRect().height}px`
    );
});
const originalScoreRanges = new Map();
let appliedParticipantsConditions = [];
let participantsFilterColumns = [];
const participantsConditionOptions = [
    ["", "Show for everyone"],
    ["contains", "Contains"],
    ["equals", "Equals"],
    ["not_equals", "Does not equal"],
    ["not_contains", "Does not contain"],
    ["empty", "Is empty"],
    ["not_empty", "Is not empty"],
    ["greater_than", "Greater than"],
    ["less_than", "Less than"],
];
const selectedParticipantColumns = new Set();


document.addEventListener(
    "DOMContentLoaded",
    function () {

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
            saveParticipantsView
        );

        document.getElementById("saveParticipantsTable").addEventListener(
            "click",
            saveParticipantsTable
        );
        document.getElementById("saveScoreChartPdf").addEventListener("click", () => {
            window.print();
        });
        showHomepageView();
    }
);


function showHomepageView() {
    const view = new URLSearchParams(window.location.search).get("view");

    if (view === "participants") {
        setActiveSidebarLink("participantsLink");
        document.getElementById("participantsTableSection").classList.remove("hidden");
        window.addEventListener("popstate", restoreParticipantsView);
        restoreParticipantsView();
        loadParticipantsTable();
    } else if (view === "summary") {
        setActiveSidebarLink("summaryLink");
        document.getElementById("summarySection").classList.remove("hidden");
        loadParticipationSummary();
    }
}


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

    participantsTableSort = null;
    participantsTableData = null;
    participantsTableView = null;
    originalScoreRanges.clear();
    updateSaveParticipantsButton();

    const message = document.getElementById(
        "participantsTableMessage"
    );
    const table = document.getElementById(
        "participantsTable"
    );

    table.classList.add(
        "hidden"
    );
    message.textContent =
        "Loading participants table...";

    try {

        const tableData =
            await fetchParticipantsTable();

        for (const group of tableData.groups) {
            for (const column of group.columns) {
                for (const range of column.interpretation_ranges || []) {
                    range.label = (range.label || "").replace(/\s*\(\s*\d+(?:\.\d+)?\s*\)/g, "").trim();
                }
                if (column.interpretation_ranges?.length) {
                    originalScoreRanges.set(column.key, { column, ranges: column.interpretation_ranges });
                }
            }
        }

        const firstTests = ["Demographics", "Location", "Occupation", "trauma-checklist", "PCL"];
        tableData.groups = [
            ...firstTests.flatMap(test => tableData.groups.filter(group => group.test === test)),
            ...tableData.groups.filter(group => !firstTests.includes(group.test)),
        ];

        participantsTableData = tableData;

        populateColumnFilter(
            tableData.fixed_columns,
            tableData.groups
        );

        restoreParticipantsView();

        table.classList.remove(
            "hidden"
        );
        initializeParticipantsColumnWidths(table);

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

    document.getElementById("showBothQuestionnairesParticipants").addEventListener("click", event => {
        const button = event.currentTarget;
        button.setAttribute("aria-pressed", button.getAttribute("aria-pressed") !== "true");
        saveParticipantsView();
    });

    addParticipantsCondition();
    document.getElementById("addParticipantsCondition").addEventListener("click", () => {
        addParticipantsCondition();
    });
    document.getElementById("participantsFilterForm").addEventListener("submit", event => {
        event.preventDefault();
        appliedParticipantsConditions = Array.from(
            document.querySelectorAll(".participants-condition-row")
        ).map(row => ({
            key: row.querySelector(".participants-condition-column").value,
            condition: row.querySelector(".participants-condition-operator").value,
            value: row.querySelector("input").value.trim(),
        })).filter(item => item.key && item.condition &&
            (item.value || ["empty", "not_empty"].includes(item.condition)));
        saveParticipantsView();
    });

    for (const id of ["testGroupFilter", "hideEmptyColumnsFilter"]) {
        document.getElementById(id).addEventListener("change", saveParticipantsView);
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


function saveParticipantsView() {
    applyParticipantsFilters();
    recordParticipantsView();
}


function recordParticipantsView() {
    const previous = {
        answeredBoth: false,
        conditions: [],
        testGroup: "",
        hiddenColumns: [],
        hideEmpty: false,
        answerLabels: false,
        selectedColumns: [],
        sort: null,
        columnWidths: [],
        scoreCutoffs: [],
        ...(window.history.state?.participantsView ?? window.history.state?.participantsFilters),
    };
    const current = {
        ...previous,
        answeredBoth: document.getElementById("showBothQuestionnairesParticipants").getAttribute("aria-pressed") === "true",
        conditions: appliedParticipantsConditions,
        hideEmpty: shouldHideEmptyColumns(),
        answerLabels: document.getElementById("showAnswerLabels").checked,
    };
    if (participantsTableData) {
        current.testGroup = document.getElementById("testGroupFilter").value;
        current.hiddenColumns = [...getHiddenColumnKeys()].sort();
        current.selectedColumns = [...selectedParticipantColumns].sort();
        current.sort = participantsTableSort;
        current.columnWidths = [...participantsColumnWidths].sort(([left], [right]) => left.localeCompare(right));
        current.scoreCutoffs = Array.from(originalScoreRanges.values())
            .filter(({ column, ranges }) => column.interpretation_ranges !== ranges)
            .map(({ column }) => [column.key, column.interpretation_ranges]);
    }
    if (JSON.stringify(current) !== JSON.stringify(previous)) {
        window.history.pushState({ participantsView: current }, "");
    }
}


function restoreParticipantsView() {
    const view = window.history.state?.participantsView ?? window.history.state?.participantsFilters;
    appliedParticipantsConditions = view?.conditions ?? [];
    document.getElementById("showBothQuestionnairesParticipants").setAttribute("aria-pressed", view?.answeredBoth === true);
    document.getElementById("hideEmptyColumnsFilter").checked = view?.hideEmpty === true;
    document.getElementById("showAnswerLabels").checked = view?.answerLabels === true;
    if (!participantsTableData) return;

    const testGroupFilter = document.getElementById("testGroupFilter");
    testGroupFilter.value = view?.testGroup ?? "";
    if (testGroupFilter.selectedIndex === -1) testGroupFilter.selectedIndex = 0;

    const hiddenColumns = new Set(view?.hiddenColumns);
    for (const checkbox of document.querySelectorAll("#hiddenColumnsFilter input[type='checkbox']")) {
        checkbox.checked = !hiddenColumns.has(checkbox.value);
    }
    selectedParticipantColumns.clear();
    for (const key of view?.selectedColumns ?? []) selectedParticipantColumns.add(key);
    participantsTableSort = view?.sort ?? null;
    participantsColumnWidths.clear();
    for (const [key, width] of view?.columnWidths ?? []) participantsColumnWidths.set(key, width);
    const scoreCutoffs = new Map(view?.scoreCutoffs);
    for (const [key, { column, ranges }] of originalScoreRanges) {
        column.interpretation_ranges = scoreCutoffs.get(key) ?? ranges;
    }
    renderAppliedParticipantsConditions();
    applyParticipantsFilters();
}


function renderAppliedParticipantsConditions() {
    document.getElementById("participantsFilterRows").replaceChildren();
    for (const item of appliedParticipantsConditions) {
        addParticipantsCondition(item);
    }
    if (!appliedParticipantsConditions.length) addParticipantsCondition();
}


function addParticipantsCondition(item) {
    const row = document.createElement("div");
    row.className = "participants-condition-row";
    const column = document.createElement("select");
    column.className = "participants-condition-column";
    column.setAttribute("aria-label", "Column");
    populateParticipantsConditionColumns(column);
    const condition = document.createElement("select");
    condition.className = "participants-condition-operator";
    condition.setAttribute("aria-label", "Condition");
    for (const [key, label] of participantsConditionOptions) {
        condition.add(new Option(label, key));
    }
    const value = document.createElement("input");
    value.type = "text";
    value.placeholder = "Filter value";
    value.setAttribute("aria-label", "Filter value");
    value.hidden = true;
    if (item) {
        column.value = item.key;
        condition.value = item.condition;
        value.value = item.value;
        value.hidden = ["empty", "not_empty"].includes(item.condition);
    }
    condition.addEventListener("change", () => {
        value.hidden = !condition.value || ["empty", "not_empty"].includes(condition.value);
    });
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "secondary-button";
    remove.textContent = "Remove";
    remove.addEventListener("click", () => {
        row.remove();
        if (!document.getElementById("participantsFilterRows").children.length) {
            addParticipantsCondition();
        }
    });
    row.append(column, condition, value, remove);
    document.getElementById("participantsFilterRows").appendChild(row);
}


function populateParticipantsConditionColumns(select) {
    const currentValue = select.value;
    select.replaceChildren(new Option("Select column", ""));
    for (const column of participantsFilterColumns) {
        select.add(new Option(column.label, column.key));
    }
    select.value = currentValue;
}


function populateColumnFilter(fixedColumns, groups) {
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

    participantsFilterColumns = columns;
    for (const select of document.querySelectorAll(".participants-condition-column")) {
        populateParticipantsConditionColumns(select);
    }

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

                saveParticipantsView();
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
                saveParticipantsView
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
                const categories = getDemographicChart(column)?.categories;
                let label = categories
                    ? categories[row[column.key]] : labels?.[column.key];

                if ((column.question || column.label || "").includes("איך נוח לך שהשאלון ינוסח")) {
                    const wordingLabels = {
                        0: "לשון זכר",
                        1: "לשון נקבה",
                    };
                    label = wordingLabels[row[column.key]];
                }
                if ((typeof row[column.key] === "number" ||
                     column.key.startsWith("occupation_")) &&
                    typeof label === "string" && label.trim()) {
                    displayedRow[column.key] = label;
                }
            }
        }
        return displayedRow;
    });
}


function sortParticipantsRows(rows, groups, fixedColumns = []) {
    if (!participantsTableSort) {
        return rows;
    }

    const { key, direction } = participantsTableSort;
    if (!fixedColumns.some(column => column.key === key) &&
        !groups.some(group => group.columns.some(column => column.key === key))) {
        participantsTableSort = null;
        return rows;
    }

    return [...rows].sort((left, right) => {
        if (["questionnaire_1_war", "questionnaire_2_war", "gave_hair"].includes(key)) {
            const comparison = String(left[key] ?? "").localeCompare(
                String(right[key] ?? ""), "en", { numeric: true }
            );
            return direction === "descending" ? -comparison : comparison;
        }
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

    const sortedRows = sortParticipantsRows(filteredRows, groups, fixedColumns);
    const displayedRows = getDisplayedParticipantsRows(sortedRows, groups);
    drawParticipantsTable(fixedColumns, groups, displayedRows);
    updateSelectedColumnsButton();

    participantsTableView = {
        fixed_columns: fixedColumns,
        groups: groups,
        rows: displayedRows,
        occupation_comparisons: participantsTableData.occupation_comparisons || {},
        filter_description: getParticipantsFilterDescription(),
    };
    updateSaveParticipantsButton();

    updateParticipantsTableMessage(
        filteredRows.length,
        participantsTableData.rows.length
    );
}


function updateSaveParticipantsButton() {
    const disabled = participantsTableSaving || !participantsTableView ||
        participantsTableView.rows.length === 0;
    const button = document.getElementById("saveParticipantsTable");
    if (button) {
        button.disabled = disabled;
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
    if (document.getElementById("showBothQuestionnairesParticipants").getAttribute("aria-pressed") === "true") {
        filters.push("Answered both questionnaires");
    }
    for (const item of appliedParticipantsConditions) {
        const columnLabel = participantsFilterColumns.find(column => column.key === item.key)?.label || item.key;
        const conditionLabel = participantsConditionOptions.find(([key]) => key === item.condition)[1];
        const needsNoValue = ["empty", "not_empty"].includes(item.condition);
        filters.push(`${columnLabel}: ${conditionLabel}${needsNoValue ? "" : ` ${item.value}`}`);
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
    if (document.getElementById("showBothQuestionnairesParticipants").getAttribute("aria-pressed") === "true" &&
        rowData.answered_both_questionnaires !== "Yes") {
        return false;
    }
    return appliedParticipantsConditions.every(item =>
        matchesColumnCondition(rowData[item.key], item.condition, item.value)
    );
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

    message.textContent = `Showing ${filteredCount} of ${totalCount} participants.`;
}


function clearParticipantsFilters() {
    appliedParticipantsConditions = [];
    document.getElementById("showBothQuestionnairesParticipants").setAttribute("aria-pressed", "false");
    renderAppliedParticipantsConditions();
    saveParticipantsView();
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
    recordParticipantsView();
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
    saveParticipantsView();
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

    saveParticipantsView();
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
    if (column.key === "gave_hair") {
        return {
            label: "Gave hair",
            categories: { Yes: "Yes", No: "No", Wait: "Wait" },
            method: "Reported hair donation status: Yes, No, or Wait. Missing values and unrecognized answers are counted separately.",
        };
    }
    if ((column.question || column.label || "").includes("מין בעת הלידה")) {
        return {
            label: "Sex at birth",
            categories: { 1: "Male", 0: "Female" },
        };
    }
    return {
        DEMOG_HEALTH_04: { label: "Age (years)", unit: "years" },
        DEMOG_HEALTH_09: { label: "Height (cm)", unit: "cm" },
        DEMOG_HEALTH_10: { label: "Weight (kg)", unit: "kg" },
    }[column.canonical_code];
}


function getDemographicChartSlices(column, data, population) {
    const rows = data.rows;
    const categories = getDemographicChart(column).categories;
    if (categories) {
        const counts = new Map(Object.values(categories).map(label => [label, 0]));
        for (const row of rows) {
            const value = row[column.key];
            const label = categories[value] || (value == null || value === ""
                ? "Missing value" : "Unclassified");
            counts.set(label, (counts.get(label) || 0) + 1);
        }
        return {
            total: rows.length,
            slices: [...counts].map(([label, count]) => ({ label, count })),
        };
    }
    const unit = getDemographicChart(column).unit;
    const binStarts = new Set();
    for (const row of population.rows) {
        const value = row[column.key];
        if (Number.isFinite(value)) {
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


function getScoreChartSlices(column, data, population = data) {
    if (getDemographicChart(column)) {
        return getDemographicChartSlices(column, data, population);
    }
    const rows = data.rows;
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
                ? getScoreInterpretation(score, categories) || "Unclassified"
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
    const chartData = {
        ...participantsTableData,
        rows: participantsTableData.rows.filter(rowMatchesParticipantsFilters),
    };
    const { total } = getScoreChartSlices(column, chartData);
    const ranges = column.interpretation_ranges || [];
    document.getElementById("scoreChartTitle").textContent = demographic
        ? demographic.label : `${testName} — ${column.label}`;
    document.getElementById("scoreChartDescription").textContent =
        demographic ? "Distribution of reported values among participants matching the applied table filters."
            : column.description?.trim() || "No subscale description is available";
    const method = column.scoring_method === "average" ? "Average" : "Sum";
    const limits = column.min_score != null && column.max_score != null
        ? ` Possible scores: ${column.min_score}–${column.max_score}.` : "";
    document.getElementById("scoreChartMethod").textContent = demographic
        ? demographic.categories
            ? demographic.method || "1 = Male; 0 = Female. Missing values and unrecognized answers are counted separately."
            : `Unit: ${demographic.unit}. Interval width: 5 ${demographic.unit}; lower bound included, upper bound excluded. Missing or nonnumeric values are included in totals as Missing value.`
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
        ? `${total} participants matching the applied table filters. `
            + (demographic ? "Grouped frequency bars show participant counts and percentages."
                : ranges.length ? "Pie chart grouped by cutoff / threshold categories."
                : "Bar plot by exact score value. Bar length shows the number of participants; no cutoff / threshold categories are defined.")
        : "No participants match the applied table filters.";
    const groups = document.getElementById("scoreChartGroups");
    groups.replaceChildren();
    const sexColumn = participantsTableData.groups.flatMap(group => group.columns)
        .find(candidate => getDemographicChart(candidate)?.label === "Sex at birth");
    for (const [title, sex] of [["All participants", null], ["Female (sex at birth)", "0"], ["Male (sex at birth)", "1"]]) {
        const data = {
            ...chartData,
            rows: chartData.rows.filter(row => sex === null || String(row[sexColumn?.key]) === sex),
        };
        drawScoreChartGroup(groups, column, data, title, chartData);
    }
    const ungrouped = chartData.rows.filter(row =>
        !["0", "1"].includes(String(row[sexColumn?.key]))
    ).length;
    if (ungrouped) {
        document.getElementById("scoreChartPopulation").textContent +=
            ` ${ungrouped} participants have missing or unrecognized sex at birth and appear only in the overall chart.`;
    }
    dialog.addEventListener("close", () => {
        if (opener.isConnected) opener.focus();
    }, { once: true });
    dialog.showModal();
}


function drawScoreChartGroup(container, column, data, title, population = data) {
    const { total, slices } = getScoreChartSlices(column, data, population);
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
        message.textContent = "No participants in this group match the applied table filters.";
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
    (header.querySelector(".question-text") || header).appendChild(button);
}


function showScoreCutoffs(column, testName) {
    const original = originalScoreRanges.get(column.key).ranges;
    const dialog = document.getElementById("scoreCutoffDialog");
    const form = document.getElementById("scoreCutoffForm");
    const fields = document.getElementById("scoreCutoffFields");
    const error = document.getElementById("scoreCutoffError");
    document.getElementById("scoreCutoffTitle").textContent = `${testName} - ${column.label}: cutoffs`;
    fields.replaceChildren();
    error.textContent = "";
    const inputs = column.interpretation_ranges.map(range => {
        const row = document.createElement("tr");
        const label = document.createElement("th");
        label.scope = "row";
        label.dir = "auto";
        label.textContent = range.label || "Unlabeled category";
        row.appendChild(label);
        const bounds = {};
        for (const [key, title] of [["min", "Minimum"], ["max", "Maximum"]]) {
            const cell = document.createElement("td");
            const input = document.createElement("input");
            input.type = "number";
            input.step = "any";
            input.required = true;
            input.value = range[key] ?? "";
            input.setAttribute("aria-label", `${label.textContent}: ${title}`);
            cell.appendChild(input);
            row.appendChild(cell);
            bounds[key] = input;
        }
        fields.appendChild(row);
        return bounds;
    });
    function applyRanges(ranges) {
        column.interpretation_ranges = JSON.stringify(ranges) === JSON.stringify(original) ? original : ranges;
        dialog.close();
        saveParticipantsView();
        const button = [...document.querySelectorAll(".score-cutoff-button")]
            .find(item => item.dataset.scoreKey === column.key);
        button?.focus();
    }
    form.onsubmit = event => {
        event.preventDefault();
        const ranges = column.interpretation_ranges.map((range, index) => ({
            ...range,
            min: inputs[index].min.valueAsNumber,
            max: inputs[index].max.valueAsNumber,
        }));
        if (ranges.some(range => !Number.isFinite(range.min) ||
            !Number.isFinite(range.max) || range.min > range.max)) {
            error.textContent = "Enter numeric boundaries with minimum less than or equal to maximum.";
            return;
        }
        const sorted = [...ranges].sort((left, right) => left.min - right.min);
        if (sorted.some((range, index) => index > 0 && range.min <= sorted[index - 1].max)) {
            error.textContent = "Ranges must not overlap. Both minimum and maximum are included.";
            return;
        }
        applyRanges(ranges);
    };
    document.getElementById("resetScoreCutoffs").onclick = () => {
        applyRanges(original);
    };
    dialog.showModal();
}


function appendScoreCutoffButton(header, column, testName) {
    if (!column.interpretation_ranges?.length) return;
    const custom = originalScoreRanges.get(column.key).ranges !== column.interpretation_ranges;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary-button score-chart-button score-cutoff-button";
    button.dataset.scoreKey = column.key;
    button.textContent = custom ? "Edit cutoffs (custom)" : "Edit cutoffs";
    button.setAttribute("aria-label", `${button.textContent} for ${testName} - ${column.label}`);
    button.addEventListener("click", () => showScoreCutoffs(column, testName));
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
    const isTextColumn = ["questionnaire_1_war", "questionnaire_2_war", "gave_hair"].includes(column.key);
    const sortOrder = isTextColumn
        ? (nextDirection === "descending" ? "Z to A" : "A to Z")
        : (nextDirection === "descending" ? "highest first" : "lowest first");
    button.setAttribute(
        "aria-label",
        `Sort ${testName} - ${column.label}: ${sortOrder}`
    );
    button.title = button.getAttribute("aria-label");
    if (direction) {
        header.setAttribute("aria-sort", direction);
    }
    button.addEventListener("click", () => {
        participantsTableSort = { key: column.key, direction: nextDirection };
        saveParticipantsView();
        const updatedButton = document.getElementById("participantsTableHead")
            .querySelector("[aria-sort] .score-sort-button");
        updatedButton?.focus();
    });
    (header.querySelector(".question-text") || header).appendChild(button);
}


function getScoreInterpretation(score, ranges) {
    if (typeof score !== "number" || !Number.isFinite(score)) {
        return "";
    }

    const matches = ranges.filter(range =>
        range.min != null &&
        range.max != null &&
        score >= range.min &&
        score <= range.max
    );

    return matches.length === 1 ? matches[0].label || "" : "";
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

    const interpretation = getScoreInterpretation(
        rowData[column.key],
        column.interpretation_ranges || []
    );

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


function applyOccupationComparison(cell, subjectId, columnKey) {
    const comparison = participantsTableData.occupation_comparisons?.[String(subjectId)];
    if (!comparison?.different_columns.includes(columnKey)) {
        return;
    }
    const automatic = comparison.automatic[columnKey];
    cell.classList.add("occupation-difference");
    cell.title += `\nAutomatic: ${automatic.code} — ${automatic.label}`;
}


function initializeParticipantsColumnWidths(table, resizing = false) {
    if (!table.offsetWidth) return;

    const handles = [...table.tHead.querySelectorAll(".participants-column-resize")];
    const naturalWidths = handles.map(handle => handle.parentElement.getBoundingClientRect().width);
    const widths = handles.map((handle, index) => {
        const naturalWidth = naturalWidths[index];
        const width = participantsColumnWidths.get(handle.dataset.columnKey) ?? naturalWidth;
        handle.dataset.columnIndex = index;
        handle.setAttribute("aria-valuemin", Math.min(80, Math.floor(naturalWidth), Math.floor(width)));
        handle.setAttribute("aria-valuemax", Math.max(1200, Math.ceil(naturalWidth), Math.ceil(width)));
        handle.setAttribute("aria-valuenow", Math.round(width));
        return width;
    });

    if (!resizing && !handles.some(handle => participantsColumnWidths.has(handle.dataset.columnKey))) {
        return;
    }

    const columns = widths.map(width => {
        const col = document.createElement("col");
        col.style.width = `${width}px`;
        return col;
    });
    document.getElementById("participantsTableColumns").replaceChildren(...columns);
    table.style.width = `${widths.reduce((total, width) => total + width, 0)}px`;
    table.classList.add("participants-columns-sized");
    participantsGroupHeaderObserver.observe(table.tHead.rows[0]);
}


function resizeParticipantsColumn(handle, requestedWidth) {
    const width = Math.min(
        Number(handle.getAttribute("aria-valuemax")),
        Math.max(Number(handle.getAttribute("aria-valuemin")), Math.round(requestedWidth))
    );
    if (width === Number(handle.getAttribute("aria-valuenow"))) return;

    const table = handle.closest("table");
    if (!table.classList.contains("participants-columns-sized")) {
        initializeParticipantsColumnWidths(table, true);
    }
    const column = document.getElementById("participantsTableColumns").children[handle.dataset.columnIndex];
    const change = width - parseFloat(column.style.width);
    column.style.width = `${width}px`;
    table.style.width = `${parseFloat(table.style.width) + change}px`;
    participantsColumnWidths.set(handle.dataset.columnKey, width);
    handle.setAttribute("aria-valuenow", width);
}


function appendParticipantsColumnResizeHandle(header, key, label) {
    const handle = document.createElement("div");
    handle.className = "participants-column-resize";
    handle.dataset.columnKey = key;
    handle.tabIndex = 0;
    handle.setAttribute("role", "separator");
    handle.setAttribute("aria-orientation", "vertical");
    handle.setAttribute("aria-label", `Resize ${label} column`);
    handle.title = `Resize ${label} (drag or use Left and Right arrow keys)`;

    let startX;
    let startWidth;
    handle.addEventListener("pointerdown", event => {
        if (!event.isPrimary || event.button !== 0) return;
        event.preventDefault();
        startX = event.clientX;
        startWidth = header.getBoundingClientRect().width;
        handle.focus({ preventScroll: true });
        handle.setPointerCapture(event.pointerId);
    });
    handle.addEventListener("pointermove", event => {
        if (handle.hasPointerCapture(event.pointerId)) {
            resizeParticipantsColumn(handle, startWidth + event.clientX - startX);
        }
    });
    handle.addEventListener("lostpointercapture", recordParticipantsView);
    handle.addEventListener("keydown", event => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        const change = event.key === "ArrowLeft" ? -10 : 10;
        resizeParticipantsColumn(handle, header.getBoundingClientRect().width + change);
    });
    handle.addEventListener("keyup", event => {
        if (event.key === "ArrowLeft" || event.key === "ArrowRight") recordParticipantsView();
    });
    header.appendChild(handle);
}


function drawParticipantsTable(fixedColumns, groups, rows) {

    fixedColumns = fixedColumns || [];

    const tableHead = document.getElementById(
        "participantsTableHead"
    );
    const tableBody = document.getElementById(
        "participantsTableBody"
    );
    const table = tableHead.closest("table");

    participantsGroupHeaderObserver.disconnect();
    table.classList.remove("participants-columns-sized");
    table.style.removeProperty("width");
    table.style.removeProperty("--participants-group-header-height");
    document.getElementById("participantsTableColumns").replaceChildren();
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
    appendParticipantsColumnResizeHandle(participantHeader, "subject_id", "subject ID");
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
        if (["questionnaire_1_war", "questionnaire_2_war", "gave_hair"].includes(column.key)) {
            appendScoreSortButton(fixedHeader, column, "Participant");
        }
        if (column.key === "gave_hair") {
            appendScoreChartButton(fixedHeader, column, "Participant");
        }
        fixedHeader.rowSpan = 2;
        fixedHeader.classList.add(
            "fixed-column-header"
        );
        appendParticipantsColumnResizeHandle(fixedHeader, column.key, column.label);
        groupHeaderRow.appendChild(
            fixedHeader
        );
    }

    for (const [groupIndex, group] of groups.entries()) {

        const groupHeader =
            document.createElement("th");
        groupHeader.textContent =
            group.test;
        groupHeader.title = group.test;
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
                appendScoreCutoffButton(codeHeader, column, group.test);
            } else if (
                ["location_district", "location_subdistrict"].includes(column.key) ||
                column.key.startsWith("occupation_")
            ) {
                appendScoreSortButton(codeHeader, column, group.test);
            } else if (getDemographicChart(column)) {
                if (getDemographicChart(column).categories) {
                    appendScoreSortButton(codeHeader, column, group.test);
                }
                appendScoreChartButton(codeHeader, column, group.test);
            }
            codeHeader.title =
                questionTooltip;
            appendColumnSelectionCheckbox(codeHeader, column, `${group.test} - ${column.label}`);

            codeHeader.classList.add(
                "canonical-code-header",
                colorClass
            );
            appendParticipantsColumnResizeHandle(codeHeader, column.key, `${group.test} - ${column.label}`);
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
            if (/^questionnaire_[12]_(started|ended)_at$/.test(column.key)) {
                cell.textContent = cell.textContent.replace("T", " ");
            }
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
            applyOccupationComparison(cell, rowData.subject_id, column.key);
            if (column.key === "occupation_review") {
                cell.classList.add("occupation-review");
            }
            if (["location_district", "location_subdistrict"].includes(column.key) &&
                rowData[column.key] === "Unknown") {
                cell.classList.add("unknown-location");
            }
            if ((["location_district", "location_subdistrict"].includes(column.key) ||
                column.canonical_code === "DEMOG_HEALTH_12") &&
                rowData.location_is_approximate) {
                cell.classList.add("approximate-location");
                cell.title += ` — Approximate locality match: ${rowData.location_matched_name}`;
            }
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
    initializeParticipantsColumnWidths(table);
}


function setActiveSidebarLink(activeLinkId) {

    const sidebarLinks =
        document.querySelectorAll(
            ".sidebar-link"
        );

    for (const link of sidebarLinks) {
        const active = link.id === activeLinkId;
        link.classList.toggle("active", active);
        if (active) {
            link.setAttribute("aria-current", "page");
        } else {
            link.removeAttribute("aria-current");
        }
    }
}

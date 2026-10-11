let participantsTableData = null;


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

        for (const group of groups || []) {
            const option = document.createElement(
                "option"
            );
            option.value = group.test;
            option.textContent = group.test;
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
                    "input[type='checkbox']:checked"
                )
            ).map(
                checkbox => checkbox.value
            )
        );

        hiddenColumnsFilter.innerHTML = "";

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
            checkbox.checked = hiddenValues.has(column.key);
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


function applyParticipantsFilters() {

    if (!participantsTableData) {
        return;
    }

    updateHiddenColumnsSummary();

    const filteredRows = participantsTableData.rows.filter(
        rowMatchesParticipantsFilters
    );

    drawParticipantsTable(
        getVisibleFixedColumns(
            participantsTableData.fixed_columns,
            filteredRows
        ),
        getVisibleGroups(
            participantsTableData.groups,
            filteredRows
        ),
        filteredRows
    );

    updateParticipantsTableMessage(
        filteredRows.length,
        participantsTableData.rows.length
    );
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
                "input[type='checkbox']:checked"
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
        if (selectedGroup && group.test !== selectedGroup) {
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


function showAllParticipantsColumns() {

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
            checkbox.checked = false;
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
        "input[type='checkbox']:checked"
    ).length;

    if (hiddenCount === 0) {
        summary.textContent = "Choose columns to hide";
    } else {
        summary.textContent = `${hiddenCount} columns hidden`;
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
            codeHeader.title =
                questionTooltip;

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
            row.appendChild(
                cell
            );
        }

        for (const column of flatColumns) {

            const cell =
                document.createElement("td");
            cell.textContent =
                rowData[column.key] ?? "";
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

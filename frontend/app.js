
const API = "/api";

let currentReviewId = null;
let toastTimer = null;
let latestAnalysisResult = null;

const $ = (id) => document.getElementById(id);


// ==================================================
// HELPERS
// ==================================================

function showToast(message, type = "success") {
    const toast = $("toast");
    if (!toast) return;

    toast.textContent = message;
    toast.className = `toast show ${type}`;

    clearTimeout(toastTimer);

    toastTimer = setTimeout(() => {
        toast.className = "toast hidden";
    }, 3000);
}

async function apiRequest(endpoint, options = {}) {
    const response = await fetch(`${API}${endpoint}`, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
        }
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(
            data.detail || `Request failed (${response.status})`
        );
    }

    return data;
}

function makeElement(tag, className = "", text = "") {
    const element = document.createElement(tag);

    if (className) element.className = className;
    if (text !== "") element.textContent = text;

    return element;
}

function makeBadge(text, className = "") {
    return makeElement("span", `badge ${className}`, text);
}

function formatDate(value) {
    if (!value) return "—";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) return value;

    return date.toLocaleString();
}

function getRiskClass(level) {
    const value = String(level || "").toLowerCase();

    if (value === "high") return "high";
    if (value === "medium") return "medium";

    return "low";
}

function getStatusClass(status) {
    const value = String(status || "").toLowerCase();

    if (value === "approved") return "approved";
    if (value.includes("change")) return "changes-requested";

    return "pending";
}


// ==================================================
// NAVIGATION
// ==================================================

function showPage(pageName) {
    document.querySelectorAll(".page").forEach((page) => {
        page.classList.remove("active");
    });

    document.querySelectorAll(".nav-link, .nav-item").forEach((link) => {
        link.classList.remove("active");
    });

    const selectedPage = $(`${pageName}-page`);

    if (!selectedPage) {
        console.error("Page not found:", pageName);
        showToast(`Could not find ${pageName} page.`, "error");
        return;
    }

    selectedPage.classList.add("active");

    const activeLink = document.querySelector(
        `.nav-link[data-page="${pageName}"], .nav-item[data-page="${pageName}"]`
    );

    if (activeLink) {
        activeLink.classList.add("active");
    }

    const titles = {
        dashboard: "Dashboard Overview",
        analyzer: "Content Analyzer",
        history: "Review History"
    };

    if ($("page-title")) {
        $("page-title").textContent =
            titles[pageName] || "BrandLens AI";
    }

    if (pageName === "dashboard") loadDashboard();
    if (pageName === "history") loadHistory();
}

document.querySelectorAll(".nav-link, .nav-item").forEach((link) => {
    link.addEventListener("click", (event) => {
        event.preventDefault();

        const pageName = link.dataset.page || link.dataset.go;

        if (pageName) showPage(pageName);
    });
});

document.querySelectorAll("[data-go]").forEach((item) => {
    item.addEventListener("click", (event) => {
        event.preventDefault();
        showPage(item.dataset.go);
    });
});

if ($("new-review-btn")) {
    $("new-review-btn").addEventListener("click", () => {
        showPage("analyzer");
    });
}


// ==================================================
// DASHBOARD
// ==================================================

async function loadStats() {
    try {
        const stats = await apiRequest("/stats");

        if ($("total-reviews")) {
            $("total-reviews").textContent = stats.total ?? 0;
        }

        if ($("pending-reviews")) {
            $("pending-reviews").textContent = stats.pending ?? 0;
        }

        if ($("high-reviews")) {
            $("high-reviews").textContent = stats.high_risk ?? 0;
        }

        if ($("approved-reviews")) {
            $("approved-reviews").textContent = stats.approved ?? 0;
        }

    } catch (error) {
        console.error("Dashboard statistics:", error);
    }
}

function buildReviewTable(reviews, targetId) {
    const container = $(targetId);
    if (!container) return;

    container.innerHTML = "";

    if (!reviews.length) {
        container.appendChild(
            makeElement(
                "div",
                "empty-state",
                "No reviews found yet. Analyse content to get started."
            )
        );
        return;
    }

    reviews.forEach((review) => {
        const row = document.createElement("tr");

        const titleCell = document.createElement("td");
        titleCell.textContent = review.title || "Untitled";

        const riskCell = document.createElement("td");

        riskCell.appendChild(
            makeBadge(
                `${review.risk_score ?? 0}% · ${review.risk_level || "Low"}`,
                `risk-${getRiskClass(review.risk_level)}`
            )
        );

        const statusCell = document.createElement("td");

        statusCell.appendChild(
            makeBadge(
                review.status || "Pending",
                `status-${getStatusClass(review.status)}`
            )
        );

        const dateCell = document.createElement("td");
        dateCell.textContent = formatDate(review.created_at);

        row.append(
            titleCell,
            riskCell,
            statusCell,
            dateCell
        );

        container.appendChild(row);
    });
}

async function loadDashboard() {
    await loadStats();

    try {
        const reviews = await apiRequest("/history");

        buildReviewTable(
            reviews.slice(0, 5),
            "recent-reviews"
        );

    } catch (error) {
        console.error("Dashboard loading:", error);
        showToast("Could not load dashboard reviews.", "error");
    }
}


// ==================================================
// WRITING INSIGHTS
// ==================================================

function updateWritingInsights() {
    const input = $("content-input");
    if (!input) return;

    const text = input.value || "";

    const words = text.trim()
        ? text.trim().split(/\s+/).length
        : 0;

    let panel = $("writing-insight");

    if (!panel) {
        panel = makeElement("div", "writing-insight");
        panel.id = "writing-insight";

        const footer = document.querySelector(".input-footer");

        if (footer) {
            footer.appendChild(panel);
        } else {
            input.insertAdjacentElement("afterend", panel);
        }
    }

    panel.textContent =
        `${words} words · ${text.length} characters`;
}

if ($("content-input")) {
    $("content-input").addEventListener("input", () => {
        if ($("char-count")) {
            $("char-count").textContent =
                `${$("content-input").value.length} / 15000`;
        }

        updateWritingInsights();
    });

    updateWritingInsights();
}


// ==================================================
// SAMPLE AND CLEAR
// ==================================================

if ($("sample-btn")) {
    $("sample-btn").addEventListener("click", () => {
        const sample =
            "Our product guarantees 100% results for everyone. " +
            "We are the number one brand in India. " +
            "Buy now before this limited time offer expires!";

        if ($("content-input")) {
            $("content-input").value = sample;
            $("content-input").dispatchEvent(new Event("input"));
        }

        if ($("content-title")) {
            $("content-title").value = "Sample Brand Content";
        }

        showToast("Sample content loaded.");
    });
}

if ($("clear-btn")) {
    $("clear-btn").addEventListener("click", () => {
        if ($("content-input")) {
            $("content-input").value = "";
            $("content-input").dispatchEvent(new Event("input"));
        }

        if ($("content-title")) {
            $("content-title").value = "";
        }

        currentReviewId = null;
        latestAnalysisResult = null;

        if ($("analysis-result")) {
            $("analysis-result").classList.add("hidden");
            $("analysis-result").style.display = "none";
        }

        showToast("Content cleared.");
    });
}


// ==================================================
// RISK INTELLIGENCE
// ==================================================

function createRiskInsights(result) {
    const panel = makeElement("section", "risk-insights");
    panel.id = "risk-insights";

    panel.append(
        makeElement("h3", "", "Risk Intelligence"),
        makeElement(
            "p",
            "",
            result.analysis_summary ||
            "Analysis completed using configured brand checks."
        )
    );

    const categories = Array.isArray(result.category_scores)
        ? result.category_scores
        : [];

    if (!categories.length) {
        panel.appendChild(
            makeElement(
                "div",
                "risk-no-findings",
                "No issues detected by configured checks. Categories without findings are not assigned a percentage."
            )
        );

        return panel;
    }

    const grid = makeElement("div", "risk-insights-grid");

    categories.forEach((category) => {
        const card = makeElement("div", "risk-insight-card");

        card.append(
            makeElement(
                "span",
                "risk-category-name",
                category.category
            ),

            makeElement(
                "strong",
                `risk-number risk-${getRiskClass(category.risk_level)}`,
                `${category.risk_score}%`
            ),

            makeElement(
                "span",
                "",
                `${category.findings_count} detected issue(s) · ${category.risk_level} risk`
            )
        );

        grid.appendChild(card);
    });

    panel.appendChild(grid);

    return panel;
}


// ==================================================
// REPORT COPYING
// ==================================================

function buildReportText(result) {
    const lines = [
        "BRANDLENS AI — CONTENT ANALYSIS REPORT",
        "--------------------------------------",
        `Title: ${result.title || "Untitled"}`,
        `Overall Risk Index: ${result.risk_score}%`,
        `Risk Level: ${result.risk_level}`,
        `Total Findings: ${result.total_findings}`,
        "",
        "ANALYSIS SUMMARY",
        result.analysis_summary || "",
        "",
        "CATEGORY SCORES"
    ];

    const categories = result.category_scores || [];

    if (!categories.length) {
        lines.push("No categories with detected findings.");
    } else {
        categories.forEach((category) => {
            lines.push(
                `${category.category}: ${category.risk_score}% (${category.risk_level})`
            );
        });
    }

    lines.push("", "DETECTED FINDINGS");

    const findings = result.findings || [];

    if (!findings.length) {
        lines.push("No issues detected by configured checks.");
    } else {
        findings.forEach((finding, index) => {
            lines.push(
                "",
                `${index + 1}. ${finding.category} — ${finding.severity}`,
                `Matched text: ${finding.matched_text}`,
                `Explanation: ${finding.explanation}`,
                `Suggestion: ${finding.suggestion}`
            );
        });
    }

    lines.push(
        "",
        "Note: Risk scores are heuristic estimates based on configured checks, not probabilities of actual brand damage."
    );

    return lines.join("\n");
}

async function copyReport(result) {
    const report = buildReportText(result);

    try {
        await navigator.clipboard.writeText(report);
        showToast("Analysis report copied.");

    } catch (error) {
        const temporary = document.createElement("textarea");

        temporary.value = report;
        document.body.appendChild(temporary);
        temporary.select();

        try {
            document.execCommand("copy");
            showToast("Analysis report copied.");
        } catch (copyError) {
            showToast("Could not copy report.", "error");
        }

        temporary.remove();
    }
}


// ==================================================
// DISPLAY ANALYSIS
// ==================================================

function displayResults(result) {
    latestAnalysisResult = result;
    currentReviewId = result.id;

    const resultContainer = $("analysis-result");

    if (resultContainer) {
        resultContainer.classList.remove("hidden");
        resultContainer.style.display = "block";
    }

    if ($("result-title")) {
        $("result-title").textContent =
            result.title || "Analysis Result";
    }

    if ($("result-score")) {
        $("result-score").textContent =
            `${result.risk_score ?? 0}`;
    }

    if ($("result-risk")) {
        $("result-risk").textContent =
            `${result.risk_level || "Low"} Risk`;

        $("result-risk").className =
            `risk-badge risk-${getRiskClass(result.risk_level)}`;
    }

    if ($("finding-count")) {
        $("finding-count").textContent =
            `${result.total_findings ?? 0} issues detected`;
    }

    const findingsList = $("findings-list");

    if (findingsList) {
        $("risk-insights")?.remove();

        const riskPanel = createRiskInsights(result);

        findingsList.parentElement?.insertBefore(
            riskPanel,
            findingsList
        );

        findingsList.innerHTML = "";

        const findings = Array.isArray(result.findings)
            ? result.findings
            : [];

        if (!findings.length) {
            findingsList.appendChild(
                makeElement(
                    "div",
                    "empty-state",
                    "No issues detected by configured checks. This does not guarantee complete brand compliance."
                )
            );

        } else {
            findings.forEach((finding) => {
                const card = makeElement("article", "finding-card");
                const header = makeElement("div", "finding-header");

                header.append(
                    makeElement(
                        "strong",
                        "finding-category",
                        finding.category
                    ),

                    makeBadge(
                        finding.severity,
                        `severity-${String(finding.severity).toLowerCase()}`
                    )
                );

                const matched = makeElement("div", "matched-text");

                matched.append(
                    makeElement(
                        "span",
                        "finding-label",
                        "Detected phrase"
                    ),

                    makeElement(
                        "strong",
                        "",
                        `"${finding.matched_text}"`
                    )
                );

                const explanation = makeElement(
                    "p",
                    "finding-explanation",
                    finding.explanation
                );

                const suggestion = makeElement(
                    "div",
                    "finding-suggestion"
                );

                suggestion.append(
                    makeElement(
                        "strong",
                        "",
                        "Suggested correction: "
                    ),

                    document.createTextNode(
                        finding.suggestion || "Review this wording."
                    )
                );

                card.append(
                    header,
                    matched,
                    explanation,
                    suggestion
                );

                findingsList.appendChild(card);
            });
        }
    }

    if (resultContainer) {
        let copyButton = $("copy-report-btn");

        if (!copyButton) {
            copyButton = makeElement(
                "button",
                "btn btn-secondary",
                "Copy Analysis Report"
            );

            copyButton.id = "copy-report-btn";

            const actions = resultContainer.querySelector(
                ".result-actions"
            );

            if (actions) {
                actions.appendChild(copyButton);
            } else {
                resultContainer.appendChild(copyButton);
            }
        }

        copyButton.onclick = () => copyReport(result);
    }

    if ($("approve-btn")) {
        $("approve-btn").disabled = false;
    }

    if ($("request-changes-btn")) {
        $("request-changes-btn").disabled = false;
    }

    if ($("review-message")) {
        $("review-message").textContent = "";
    }

    resultContainer?.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}


// ==================================================
// ANALYZE FORM
// ==================================================

if ($("analysis-form")) {
    $("analysis-form").addEventListener("submit", async (event) => {
        event.preventDefault();

        const content = $("content-input")?.value.trim() || "";

        const title = $("content-title")?.value.trim()
            || "Untitled Content";

        if (content.length < 3) {
            showToast("Please enter content to analyse.", "error");
            return;
        }

        const button = $("analyze-btn");

        const originalText = button?.textContent
            || "Analyze Brand Compliance";

        if (button) {
            button.disabled = true;
            button.textContent = "Analysing content...";
        }

        try {
            const result = await apiRequest("/analyze", {
                method: "POST",
                body: JSON.stringify({
                    title,
                    content
                })
            });

            displayResults(result);

            showToast("Brand compliance analysis completed!");

            await loadStats();

        } catch (error) {
            console.error("Analysis error:", error);
            showToast(error.message || "Analysis failed.", "error");

        } finally {
            if (button) {
                button.disabled = false;
                button.textContent = originalText;
            }
        }
    });
}


// ==================================================
// HUMAN REVIEW
// ==================================================

async function submitReviewAction(action) {
    if (!currentReviewId) {
        showToast("Analyse content before reviewing.", "error");
        return;
    }

    const note = $("review-note")?.value.trim() || "";

    const approveButton = $("approve-btn");
    const changesButton = $("request-changes-btn");

    if (approveButton) approveButton.disabled = true;
    if (changesButton) changesButton.disabled = true;

    try {
        const result = await apiRequest(
            `/reviews/${currentReviewId}`,
            {
                method: "PATCH",
                body: JSON.stringify({
                    action,
                    note
                })
            }
        );

        if ($("review-message")) {
            $("review-message").textContent = result.message;
        }

        showToast(result.message || "Review updated.");

        await loadStats();
        await loadHistory();

    } catch (error) {
        console.error("Review update:", error);
        showToast(error.message || "Review update failed.", "error");

    } finally {
        if (approveButton) approveButton.disabled = false;
        if (changesButton) changesButton.disabled = false;
    }
}

if ($("approve-btn")) {
    $("approve-btn").addEventListener("click", () => {
        submitReviewAction("approve");
    });
}

if ($("request-changes-btn")) {
    $("request-changes-btn").addEventListener("click", () => {
        submitReviewAction("request_changes");
    });
}


// ==================================================
// REVIEW HISTORY — FIXED
// ==================================================

async function loadHistory() {
    const container = $("history-table");

    if (!container) return;

    container.innerHTML = `
        <div class="empty-state">Loading review history...</div>
    `;

    try {
        const reviews = await apiRequest("/history");

        buildHistoryTable(reviews);

    } catch (error) {
        console.error("History loading:", error);

        container.innerHTML = "";

        container.appendChild(
            makeElement(
                "div",
                "empty-state",
                "Unable to load history. Please check your backend connection."
            )
        );

        showToast("Could not load review history.", "error");
    }
}


// IMPORTANT: Your HTML has a DIV container, not a TABLE.
// This function creates the table inside that DIV.

function buildHistoryTable(reviews) {
    const container = $("history-table");

    if (!container) return;

    container.innerHTML = "";

    if (!Array.isArray(reviews) || reviews.length === 0) {
        container.appendChild(
            makeElement(
                "div",
                "empty-state",
                "No review history available. Analyse some content to get started."
            )
        );

        return;
    }

    const table = document.createElement("table");
    table.className = "history-data-table";

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");

    const headings = [
        "Content Title",
        "Risk Score",
        "Status",
        "Date"
    ];

    headings.forEach((heading) => {
        const th = document.createElement("th");
        th.textContent = heading;
        headerRow.appendChild(th);
    });

    thead.appendChild(headerRow);

    const tbody = document.createElement("tbody");

    reviews.forEach((review) => {
        const row = document.createElement("tr");

        const titleCell = document.createElement("td");
        titleCell.textContent = review.title || "Untitled";

        const riskCell = document.createElement("td");

        riskCell.appendChild(
            makeBadge(
                `${review.risk_score ?? 0}% · ${review.risk_level || "Low"}`,
                `risk-${getRiskClass(review.risk_level)}`
            )
        );

        const statusCell = document.createElement("td");

        statusCell.appendChild(
            makeBadge(
                review.status || "Pending",
                `status-${getStatusClass(review.status)}`
            )
        );

        const dateCell = document.createElement("td");
        dateCell.textContent = formatDate(review.created_at);

        row.append(
            titleCell,
            riskCell,
            statusCell,
            dateCell
        );

        tbody.appendChild(row);
    });

    table.append(thead, tbody);

    container.appendChild(table);
}


// Refresh button

if ($("refresh-history")) {
    $("refresh-history").addEventListener("click", () => {
        loadHistory();
    });
}


// ==================================================
// APPLICATION STARTUP
// ==================================================

async function startApplication() {
    try {
        const health = await apiRequest("/health");

        console.log(
            `${health.application} connected — version ${health.version}`
        );

        await loadDashboard();

    } catch (error) {
        console.error("Application startup:", error);

        showToast(
            "Backend connection failed. Check the server.",
            "error"
        );
    }
}

startApplication();

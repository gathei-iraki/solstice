const form = document.querySelector("#scan-form");
const input = document.querySelector("#qr-code");
const button = form.querySelector("button");
const result = document.querySelector("#result");
const statusLabel = document.querySelector("#status-label");
const attendeeName = document.querySelector("#attendee-name");
const detail = document.querySelector("#detail");

const csrfToken = form.querySelector(
    "[name=csrfmiddlewaretoken]"
).value;

let pollTimer;

function showResult(data) {
    let stateClass = "";

    if (data.status === "succeeded") {
        stateClass = "success";
    } else if (data.status === "failed") {
        stateClass = "failed";
    }

    result.className = `result ${stateClass}`;
    statusLabel.textContent =
        data.message || "Unable to check in";
    attendeeName.textContent = data.attendee || "";

    if (data.status === "pending") {
        detail.textContent = data.duplicate
            ? "This badge request already exists. Waiting for the printer…"
            : "Badge requested. Waiting for printer confirmation…";
    } else if (data.status === "succeeded") {
        detail.textContent = "Badge printed successfully.";
    } else {
        detail.textContent =
            data.error ||
            "Please ask a staff member for help.";
    }
}

async function pollJob(jobId) {
    try {
        const response = await fetch(`/api/jobs/${jobId}/`);
        const data = await response.json();

        if (!response.ok) {
            throw data;
        }

        showResult(data);

        if (data.status === "pending") {
            pollTimer = setTimeout(
                () => pollJob(jobId),
                1500
            );
        } else {
            button.disabled = false;
            input.value = "";
            input.focus();
        }
    } catch (error) {
        showResult({
            status: "failed",
            message: error.error || "Unable to get job status",
        });

        button.disabled = false;
    }
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearTimeout(pollTimer);
    button.disabled = true;

    try {
        const response = await fetch("/api/scans/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify({
                qr_code: input.value,
            }),
        });

        const data = await response.json();

        if (!response.ok) {
            throw data;
        }

        showResult(data);

        if (data.status === "pending") {
            pollJob(data.job_id);
        } else {
            button.disabled = false;
        }
    } catch (error) {
        showResult({
            status: "failed",
            message: error.error || "Network error",
        });

        button.disabled = false;
    }
});
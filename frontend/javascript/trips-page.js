// trips-page.js
// Only for trips.html.
// Job: get the trips from the backend, draw one row per trip, filter by tab.

function normalizeTrip(raw) {
    return {
        id: raw.reference,
        requestedAt: raw.createdAt,
        pickup: raw.pickupName,
        dropoff: raw.destinationName,
        fare: raw.priceEur,
        currency: "EUR", //
        status: String(raw.status || "").toLowerCase(),
    };
}

// ---------- 2. PAGE ELEMENTS ----------

const tripsList = document.getElementById("tripsList");
const tripsMsg = document.getElementById("tripsMsg");
const tripTemplate = document.getElementById("tripTemplate");
const tabs = document.querySelectorAll(".trips-tab");

let allTrips = [];
let activeFilter = "all";

// ---------- 3. FORMATTING HELPERS ----------

function sameDay(a, b) {
    return (
        a.getFullYear() === b.getFullYear() &&
        a.getMonth() === b.getMonth() &&
        a.getDate() === b.getDate()
    );
}

// "Today, 9:42 AM", "Yesterday, 7:16 PM", or "Oct 24, 2025, 4:03 PM"
function formatWhen(isoText) {
    const date = new Date(isoText);
    if (Number.isNaN(date.getTime())) return "Date unavailable";

    const time = date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    const now = new Date();
    const yesterday = new Date();
    yesterday.setDate(now.getDate() - 1);

    if (sameDay(date, now)) return "Today, " + time;
    if (sameDay(date, yesterday)) return "Yesterday, " + time;

    const day = date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
    });
    return day + ", " + time;
}

function formatFare(fare, currency) {
    if (typeof fare !== "number") return "";
    if (currency) {
        try {
            return new Intl.NumberFormat("en", {
                style: "currency",
                currency: currency,
            }).format(fare);
        } catch (error) {
            // unknown currency code, fall through to the plain number
        }
    }
    return fare.toLocaleString();
}

function statusLabel(status) {
    if (!status) return "";
    return status.charAt(0).toUpperCase() + status.slice(1);
}

// ---------- 4. DRAWING ----------

function showMessage(text) {
    tripsMsg.textContent = text;
}

function renderTrips() {
    const visible =
        activeFilter === "all"
            ? allTrips
            : allTrips.filter((trip) => trip.status === activeFilter);

    tripsList.replaceChildren();

    if (visible.length === 0) {
        if (allTrips.length > 0) showMessage("No " + activeFilter + " trips to show.");
        return;
    }
    showMessage("");

    visible.forEach((trip) => {
        const row = tripTemplate.content.firstElementChild.cloneNode(true);

        // textContent (not innerHTML) so text from the backend can never run as code.
        row.querySelector(".trip-when").textContent = formatWhen(trip.requestedAt);
        row.querySelector(".trip-from").textContent = trip.pickup || "Unknown pickup";
        row.querySelector(".trip-to").textContent = trip.dropoff || "Unknown dropoff";
        row.querySelector(".trip-fare").textContent = formatFare(trip.fare, trip.currency);

        const badge = row.querySelector(".trip-status");
        badge.textContent = statusLabel(trip.status);
        if (trip.status) badge.classList.add("status-" + trip.status);

        tripsList.appendChild(row);
    });
}

// ---------- 5. LOADING FROM THE BACKEND ----------

async function loadTrips() {
    if (!window.ApiClient) {
        showMessage("The page could not reach the API helper. Please reload the page.");
        return;
    }

    showMessage("Loading your trips...");

    try {
        const data = await window.ApiClient.apiRequest("/trips");
        if (!Array.isArray(data)) throw new Error("Expected a list of trips");

        allTrips = data.map(normalizeTrip);
        if (allTrips.length === 0) {
            showMessage("You have no trips yet.");
            return;
        }
        renderTrips();
    } catch (error) {
        console.error("Could not load trips:", error);
        showMessage("We could not load your trips. Please try again later.");
    }
}

// ---------- 6. TABS ----------

tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
        activeFilter = tab.dataset.filter;
        tabs.forEach((t) => {
            const active = t === tab;
            t.classList.toggle("active", active);
            t.setAttribute("aria-selected", String(active));
        });
        if (allTrips.length > 0) renderTrips();
    });
});

window.addEventListener("DOMContentLoaded", loadTrips);

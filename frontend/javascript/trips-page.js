// trips-page.js
// Only for trips.html.
// Job: get the trips from the backend, draw one row per trip, filter by tab.
// No sample data lives here. Until TRIPS_API_URL is filled in, the page
// shows a "not connected yet" message.

// ---------- 1. SETTINGS (fill these in when the backend is ready) ----------

// The address of your trips endpoint, for example "https://your-api.example.com/trips".
const TRIPS_API_URL = "";

// The ONLY place that knows the backend's field names.
// If your backend uses different names, change them here and nothing else.
function normalizeTrip(raw) {
    return {
        id: raw.id,
        requestedAt: raw.requestedAt, // a date and time text like "2026-11-04T09:42:00Z"
        pickup: raw.pickup,           // text
        dropoff: raw.dropoff,         // text
        fare: raw.fare,               // a number
        currency: raw.currency,       // like "EUR" or "NGN"
        status: String(raw.status || "").toLowerCase(), // "completed" or "cancelled"
    };
}

// Later, when your API needs the login token, return it here, like
// { Authorization: "Bearer <token>" }. auth.js has no token method yet,
// so for now this sends nothing extra.
async function getAuthHeaders() {
    return {};
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
                maximumFractionDigits: 0,
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
    if (!TRIPS_API_URL) {
        showMessage("Trips are not connected yet. They will show here once the backend is ready.");
        return;
    }

    showMessage("Loading your trips...");

    try {
        const response = await fetch(TRIPS_API_URL, { headers: await getAuthHeaders() });
        if (!response.ok) throw new Error("Server answered " + response.status);

        const data = await response.json();
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

loadTrips();

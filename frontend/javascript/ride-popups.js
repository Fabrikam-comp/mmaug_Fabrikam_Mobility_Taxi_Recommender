/* Ride popups: shows the ride options, the booking confirmation and the result.
   It is connected to ride-popups.html (the markup) and css/ride-popups.css.
   It holds no sample data: everything comes from the API.

   How ride-page.js uses it, when the user presses "Find a ride":
     RidePopup.findRide(journey, { pickupLabel: "Valletta", destinationLabel: "Sliema" });
   where journey is the POST /quotes body:
     { pickup: {lat, lon}, destination: {lat, lon}, passengers, load, currency, preferredProvider? }
   If you already have the /quotes answer, show it with:
     RidePopup.open(quotesResponse, { pickupLabel, destinationLabel });  */

// ============================================================
// PLACEHOLDER IMPORT: replace this line with your real API client.
//
// What this file expects from it:
//   apiRequest(path, { method, body, headers }) -> the parsed JSON answer
//   - path starts with "/" (for example "/quotes"). The client adds the API address.
//   - body is a plain object. The client turns it into JSON.
//   - the client adds "Authorization: Bearer <ID token>" itself.
//   - on an error it throws an Error that has: status, code, message, details, retryAfter
//       code    = detail.code from the API (for example "QUOTE_EXPIRED")
//       details = the whole detail object (for example { code, message, reference })
//       retryAfter = seconds from the Retry-After header, if any
// ============================================================
import { apiRequest } from "./api-client.js";

const TRIPS_URL = "trips.html"; // where "View my trips" goes

// Points for each factor. They match the weights in scoring/ranking.py.
const SCORE_MAX = { proximity: 30, fit: 30, preference: 25, price: 15 };
const SCORE_LABEL = {
    proximity: "Pickup time",
    fit: "Fits your group and bags",
    preference: "Preferred provider",
    price: "Price",
};

const state = {
    open: false,
    data: null, // the /quotes answer
    journey: null, // the /quotes request, when findRide was used
    labels: {}, // pickupLabel, destinationLabel
    selected: null, // the option chosen with Book
    inFlight: false, // a booking request is running
    runId: 0, // makes late answers from an old search or a closed popup harmless
    keys: new Map(), // quoteId -> Idempotency-Key (the same quote always uses the same key)
    timer: null,
    lastFocus: null,
    expiredShown: false,
};

const $ = (id) => document.getElementById(id);

// ---------- small helpers (text is always set with textContent, never as HTML) ----------

function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
}

function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
}

function detailRow(label, value, className) {
    const row = el("div", "rp-detail" + (className ? " " + className : ""));
    row.appendChild(el("dt", "", label));
    const dd = el("dd");
    if (value instanceof Node) dd.appendChild(value);
    else dd.textContent = value;
    row.appendChild(dd);
    return row;
}

function minutes(value) {
    return Math.max(1, Math.round(Number(value))) + " min";
}

function shortDate(iso) {
    const date = new Date(String(iso).slice(0, 10) + "T00:00:00");
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

function tidy(id) {
    return String(id).split(/[\s_-]+/).filter(Boolean).map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

function nameOf(providerId) {
    const found = (state.data?.providers || []).find((p) => p.providerId === providerId);
    return found?.name || tidy(providerId);
}

function vehicleText(option) {
    const kind = option.vehicleClass === "XL" ? "XL" : "Standard";
    const seats = option.seats + (option.seats === 1 ? " seat" : " seats");
    const bags = option.bagCapacity + (option.bagCapacity === 1 ? " bag" : " bags");
    return `${kind} - ${seats} - ${bags}`;
}

function isBookable(item) {
    const price = item.option.price;
    return price.status !== "UNAVAILABLE" && price.amountEur !== null && price.amountEur !== undefined;
}

function priceCell(item) {
    const wrap = el("span");
    if (!isBookable(item)) {
        wrap.textContent = "Price not available";
        return wrap;
    }
    const eur = item.option.price;
    wrap.appendChild(el("span", "", "EUR " + Number(eur.amountEur).toFixed(2)));
    if (eur.status === "ESTIMATE") wrap.appendChild(el("span", "rp-sub", "Estimate"));
    const conv = item.convertedPrice;
    if (conv) {
        wrap.appendChild(el("span", "rp-sub rp-converted", `\u2248 ${conv.currency} ${Number(conv.amount).toFixed(2)}`));
        const when = shortDate(conv.rateDate);
        wrap.appendChild(el("span", "rp-sub", "ECB rate" + (when ? ", " + when : "")));
    }
    return wrap;
}

function remainingMs(expiresAt) {
    return Date.parse(expiresAt) - Date.now();
}

function formatRemaining(ms) {
    if (!(ms > 0)) return "Expired";
    const total = Math.ceil(ms / 1000);
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

function timerNode(expiresAt) {
    const node = el("span", "rp-timer", formatRemaining(remainingMs(expiresAt)));
    node.dataset.expires = expiresAt;
    if (!(remainingMs(expiresAt) > 0)) node.classList.add("rp-expired");
    return node;
}

function makeKey() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") return window.crypto.randomUUID();
    const bytes = new Uint8Array(16);
    if (window.crypto && window.crypto.getRandomValues) window.crypto.getRandomValues(bytes);
    else for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
    return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

// One Idempotency-Key per quote. A retry or a double click on the same quote
// sends the same key, so the server never makes a second booking.
function keyFor(quoteId) {
    if (!state.keys.has(quoteId)) state.keys.set(quoteId, makeKey());
    return state.keys.get(quoteId);
}

// ---------- error messages ----------

function describeError(error) {
    const code = error?.code || error?.details?.code || error?.detail?.code;
    const status = error?.status;
    const retry = Number(error?.retryAfter);
    switch (code) {
        case "QUOTE_EXPIRED":
        case "QUOTE_NOT_FOUND":
            return { message: "This quote is no longer available. Please search again.", searchAgain: true };
        case "QUOTE_NOT_BOOKABLE":
            return { message: "This option cannot be booked. Please choose another one." };
        case "PROVIDER_UNAVAILABLE":
            return {
                message:
                    "The provider could not confirm the booking right now. Please try again" +
                    (retry > 0 ? ` in about ${Math.ceil(retry)} seconds.` : "."),
            };
        case "TRIP_SAVE_FAILED": {
            const ref = error?.details?.reference || error?.detail?.reference;
            return {
                message:
                    "Your booking was confirmed" +
                    (ref ? ` (reference ${ref})` : "") +
                    " but could not be saved to your trips. Press Confirm booking again to finish it.",
            };
        }
        case "INVALID_IDEMPOTENCY_KEY":
        case "IDEMPOTENCY_KEY_REUSED":
            if (state.selected) state.keys.delete(state.selected.option.quoteId);
            return { message: "Something went wrong with this booking. Please try again." };
        case "CONFIRMATION_REQUIRED":
            return { message: "Please tick the box to confirm the booking." };
        case "OUTSIDE_MALTA":
            return { message: "The pickup point and the destination must both be inside Malta." };
        case "UNKNOWN_PROVIDER":
            return { message: "The preferred provider is not known. Please choose another one." };
        default:
            break;
    }
    if (status === 401 || status === 403) return { message: "Your session has ended. Please sign in again." };
    if (error instanceof TypeError) return { message: "We could not reach the service. Check your connection and try again." };
    return { message: error?.message || "Something went wrong. Please try again." };
}

function bannerNode(kind, message, extra) {
    const banner = el("div", "rp-banner rp-" + kind);
    banner.appendChild(el("span", "rp-banner-icon", kind === "info" ? "i" : "!"));
    const text = el("div", "rp-banner-text");
    text.appendChild(el("span", "", message));
    if (extra) text.appendChild(extra);
    banner.appendChild(text);
    return banner;
}

// ---------- steps and the overlay ----------

function showStep(name) {
    ["results", "confirm", "done"].forEach((step) => {
        $("rp-step-" + step).hidden = step !== name;
    });
    $("rp-dialog").setAttribute("aria-labelledby", "rp-title-" + name);
    const body = $("rp-step-" + name).querySelector(".rp-body");
    if (body) body.scrollTop = 0;
    const title = $("rp-title-" + name);
    if (title) title.focus();
}

function openOverlay() {
    if (!state.open) {
        state.lastFocus = document.activeElement;
        state.open = true;
        $("rp-overlay").hidden = false;
        document.body.classList.add("rp-lock");
        state.timer = setInterval(tick, 1000);
    }
}

function close() {
    if (state.inFlight) return false; // never close while a booking request is running
    if (!state.open) return true;
    state.open = false;
    state.runId += 1; // answers that arrive later are ignored
    clearInterval(state.timer);
    state.timer = null;
    $("rp-overlay").hidden = true;
    document.body.classList.remove("rp-lock");
    if (state.lastFocus && typeof state.lastFocus.focus === "function") state.lastFocus.focus();
    return true;
}

function searchAgain() {
    if (state.journey && !state.inFlight) {
        findRide(state.journey, state.labels);
        return;
    }
    if (close()) document.dispatchEvent(new CustomEvent("ridepopup:searchagain"));
}

// Runs every second: updates the quote countdowns and disables Book when a quote expires.
function tick() {
    document.querySelectorAll("#rp-overlay .rp-timer").forEach((node) => {
        const ms = remainingMs(node.dataset.expires);
        node.textContent = formatRemaining(ms);
        node.classList.toggle("rp-expired", !(ms > 0));
    });
    document.querySelectorAll("#rp-overlay [data-book-expires]").forEach((button) => {
        const expired = !(remainingMs(button.dataset.bookExpires) > 0);
        button.disabled = expired;
        button.textContent = expired ? "Quote expired" : "Book this ride";
    });
    if (!$("rp-step-confirm").hidden) updateConfirmState();
}

// ---------- step 1: the ride options ----------

function renderTrip() {
    const trip = $("rp-trip");
    clear(trip);
    trip.appendChild(detailRow("Pickup point", state.labels.pickupLabel || "Your pickup point"));
    trip.appendChild(detailRow("Destination", state.labels.destinationLabel || "Your destination"));
    const passengers = state.journey?.passengers ?? state.labels.passengers;
    const bags = state.journey?.load ?? state.labels.bags;
    if (passengers !== undefined) trip.appendChild(detailRow("Passengers", String(passengers)));
    if (bags !== undefined) trip.appendChild(detailRow("Bags", String(bags)));
}

function showStatus(kind, error) {
    const box = $("rp-status");
    clear(box);
    if (kind === "loading") {
        const row = el("div", "rp-loading");
        row.appendChild(el("span", "rp-spinner"));
        row.appendChild(el("span", "", "Looking for rides..."));
        box.appendChild(row);
    } else if (kind === "error") {
        const retry = el("button", "rp-btn", "Try again");
        retry.type = "button";
        retry.addEventListener("click", () => findRide(state.journey, state.labels));
        box.appendChild(bannerNode("error", describeError(error).message, state.journey ? retry : null));
    }
}

function clearResults() {
    ["rp-banners", "rp-recommended", "rp-others", "rp-more", "rp-status"].forEach((id) => clear($(id)));
    $("rp-explain").hidden = true;
    $("rp-others-title").hidden = true;
    $("rp-more").hidden = true;
    $("rp-more-toggle").hidden = true;
    $("rp-more-toggle").setAttribute("aria-expanded", "false");
}

const REASON_TEXT = {
    TIMEOUT: "is not responding",
    RATE_LIMITED: "is busy right now",
    CIRCUIT_OPEN: "is temporarily unavailable",
    ERROR: "had a problem",
};

function renderBanners(hasOptions) {
    const box = $("rp-banners");
    (state.data.providers || []).forEach((provider) => {
        if (!provider.reason) return;
        const what = REASON_TEXT[provider.reason] || "is unavailable";
        box.appendChild(bannerNode("warn", `${provider.name || tidy(provider.providerId)} ${what}.` + (hasOptions ? " Showing the other options." : "")));
    });
    if (state.data.currencyNotice) box.appendChild(bannerNode("info", state.data.currencyNotice));
}

function scorePanel(score) {
    const wrap = el("div", "rp-score");
    const toggle = el("button", "rp-link", "Why this score");
    toggle.type = "button";
    toggle.setAttribute("aria-expanded", "false");
    const panel = el("div", "rp-score-panel");
    panel.hidden = true;
    Object.keys(SCORE_MAX).forEach((key) => {
        const factor = el("div", "rp-factor");
        const top = el("div", "rp-factor-top");
        top.appendChild(el("span", "", SCORE_LABEL[key]));
        top.appendChild(el("span", "", `${Number(score[key]).toFixed(1)} / ${SCORE_MAX[key]}`));
        const bar = el("div", "rp-bar");
        const fill = document.createElement("i");
        fill.style.width = Math.max(0, Math.min(100, (Number(score[key]) / SCORE_MAX[key]) * 100)) + "%";
        bar.appendChild(fill);
        factor.appendChild(top);
        factor.appendChild(bar);
        panel.appendChild(factor);
    });
    const total = el("div", "rp-total");
    total.appendChild(el("span", "", "Total"));
    total.appendChild(el("span", "", `${Number(score.total).toFixed(1)} / 100`));
    panel.appendChild(total);
    toggle.addEventListener("click", () => {
        const opening = panel.hidden;
        panel.hidden = !opening;
        toggle.setAttribute("aria-expanded", String(opening));
    });
    wrap.appendChild(toggle);
    wrap.appendChild(panel);
    return wrap;
}

function optionCard(item, recommended) {
    const option = item.option;
    const card = el("article", "rp-card" + (recommended ? " rp-recommended" : ""));
    if (recommended) card.appendChild(el("span", "rp-tag", "RECOMMENDED"));

    const head = el("div", "rp-card-head");
    head.appendChild(el("strong", "rp-card-title", nameOf(option.providerId)));
    head.appendChild(el("span", "rp-pill", option.dataSource || "SIMULATED"));
    if (option.providerStatus === "SLOW") head.appendChild(el("span", "rp-pill", "SLOW"));
    card.appendChild(head);

    const list = el("dl", "rp-details");
    list.appendChild(detailRow("Vehicle", vehicleText(option)));
    list.appendChild(detailRow("Price", priceCell(item)));
    list.appendChild(detailRow("Pickup in", minutes(option.pickupEtaMin)));
    list.appendChild(detailRow("Trip time", minutes(option.journeyMin)));
    list.appendChild(detailRow("Quote valid for", timerNode(option.expiresAt)));
    card.appendChild(list);

    if (item.score) card.appendChild(scorePanel(item.score));

    if (isBookable(item)) {
        const expired = !(remainingMs(option.expiresAt) > 0);
        const book = el("button", "rp-btn rp-primary rp-block", expired ? "Quote expired" : "Book this ride");
        book.type = "button";
        book.disabled = expired;
        book.dataset.bookExpires = option.expiresAt;
        book.addEventListener("click", () => openConfirm(item));
        card.appendChild(book);
    } else {
        card.appendChild(el("p", "rp-muted-note", "Price not available, so this option cannot be booked."));
    }
    return card;
}

function renderResults() {
    clearResults();
    const data = state.data;
    const top = data.topOptions || [];
    const all = data.allOptions || [];
    renderBanners(top.length > 0);

    if (top.length === 0) {
        const empty = el("div", "rp-empty");
        empty.appendChild(el("p", "", "No ride options are available right now."));
        const again = el("button", "rp-btn", "Search again");
        again.type = "button";
        again.addEventListener("click", searchAgain);
        empty.appendChild(again);
        $("rp-recommended").appendChild(empty);
        return;
    }

    const winner = top.find((item) => item.recommended) || top[0];
    $("rp-recommended").appendChild(optionCard(winner, true));

    const others = top.filter((item) => item !== winner);
    if (others.length) {
        $("rp-others-title").hidden = false;
        others.forEach((item) => $("rp-others").appendChild(optionCard(item, false)));
    }

    const shown = new Set(top.map((item) => item.option.quoteId));
    const rest = all.filter((item) => !shown.has(item.option.quoteId));
    if (rest.length) {
        rest.forEach((item) => $("rp-more").appendChild(optionCard(item, false)));
        $("rp-more-toggle").hidden = false;
    }

    loadExplanation(data.quoteSetId);
}

async function loadExplanation(quoteSetId) {
    if (!quoteSetId) return;
    const run = state.runId;
    const box = $("rp-explain");
    const text = $("rp-explain-text");
    $("rp-explain-ai").hidden = true;
    text.className = "rp-muted-note";
    text.textContent = "Writing a short explanation...";
    box.hidden = false;
    try {
        const answer = await apiRequest("/explanations/" + encodeURIComponent(quoteSetId));
        if (run !== state.runId || !state.open) return;
        text.className = "";
        text.textContent = answer.text;
        $("rp-explain-ai").hidden = answer.source !== "AI"; // the label is shown only for AI text
    } catch (error) {
        if (run === state.runId) box.hidden = true; // no explanation is not a problem, just hide the panel
    }
}

// ---------- step 2: confirm ----------

function renderConfirm() {
    const item = state.selected;
    const option = item.option;
    const list = $("rp-confirm-details");
    clear(list);
    list.appendChild(detailRow("Provider", nameOf(option.providerId)));
    list.appendChild(detailRow("Vehicle", vehicleText(option)));
    list.appendChild(detailRow("Pickup point", state.labels.pickupLabel || "Your pickup point"));
    list.appendChild(detailRow("Destination", state.labels.destinationLabel || "Your destination"));
    list.appendChild(detailRow("Price", priceCell(item)));
    list.appendChild(detailRow("Pickup in", minutes(option.pickupEtaMin)));
    list.appendChild(detailRow("Trip time", minutes(option.journeyMin)));
    list.appendChild(detailRow("Quote valid for", timerNode(option.expiresAt)));
}

function clearConfirmError() {
    clear($("rp-confirm-error"));
}

function showConfirmError(error) {
    const info = describeError(error);
    const box = $("rp-confirm-error");
    clear(box);
    let action = null;
    if (info.searchAgain) {
        action = el("button", "rp-btn", "Search again");
        action.type = "button";
        action.addEventListener("click", searchAgain);
    }
    box.appendChild(bannerNode("error", info.message, action));
}

function updateConfirmState() {
    const button = $("rp-confirm");
    const expired = state.selected ? !(remainingMs(state.selected.option.expiresAt) > 0) : true;
    button.disabled = state.inFlight || expired || !$("rp-confirm-check").checked;
    if (expired && state.selected && !state.expiredShown) {
        state.expiredShown = true;
        showConfirmError({ code: "QUOTE_EXPIRED" });
    }
}

function openConfirm(item) {
    state.selected = item;
    state.expiredShown = false;
    $("rp-confirm-check").checked = false;
    document.querySelector('input[name="rp-pay"][value="CARD_SIMULATED"]').checked = true;
    clearConfirmError();
    renderConfirm();
    showStep("confirm");
    updateConfirmState();
}

function setBusy(busy) {
    state.inFlight = busy;
    const button = $("rp-confirm");
    clear(button);
    if (busy) {
        button.appendChild(el("span", "rp-spinner"));
        button.appendChild(el("span", "", "Booking..."));
    } else {
        button.textContent = "Confirm booking";
    }
    document.querySelectorAll("#rp-overlay [data-rp-close]").forEach((b) => (b.disabled = busy));
    $("rp-back").disabled = busy;
    updateConfirmState();
}

function chosenPayment() {
    const picked = document.querySelector('input[name="rp-pay"]:checked');
    return picked ? picked.value : "CARD_SIMULATED";
}

async function confirmBooking() {
    if (state.inFlight || !state.selected) return;
    const item = state.selected;
    const quoteId = item.option.quoteId;
    const payment = chosenPayment();
    clearConfirmError();
    setBusy(true);
    try {
        const booking = await apiRequest("/bookings", {
            method: "POST",
            body: { quoteId, confirmed: true, paymentMethod: payment },
            headers: { "Idempotency-Key": keyFor(quoteId) },
        });
        renderDone(booking, item, payment);
        showStep("done");
    } catch (error) {
        showConfirmError(error);
    } finally {
        setBusy(false);
    }
}

// ---------- step 3: booking confirmed ----------

function renderDone(booking, item, payment) {
    const option = item.option;
    const list = $("rp-done-details");
    clear(list);
    list.appendChild(detailRow("Reference", booking.reference, "rp-ref"));
    list.appendChild(detailRow("Provider", nameOf(booking.providerId || option.providerId)));
    list.appendChild(detailRow("Vehicle", vehicleText(option)));
    list.appendChild(detailRow("Pickup point", state.labels.pickupLabel || booking.pickupName || ""));
    list.appendChild(detailRow("Destination", state.labels.destinationLabel || booking.destinationName || ""));
    const price = el("span");
    price.textContent = "EUR " + Number(booking.priceEur ?? option.price.amountEur).toFixed(2);
    list.appendChild(detailRow("Price", price));
    list.appendChild(detailRow("Payment", payment === "CASH" ? "Cash" : "Card (simulated)"));
    list.appendChild(detailRow("Status", booking.status === "CONFIRMED" || !booking.status ? "Confirmed" : String(booking.status)));
    $("rp-done-note").textContent = booking.alreadyBooked
        ? "This booking was already confirmed earlier. Simulated, nothing was charged."
        : "Simulated. Nothing was charged.";
}

function goToTrips() {
    // Another script can cancel this event to handle the navigation itself.
    const goAhead = document.dispatchEvent(new CustomEvent("ridepopup:viewtrips", { cancelable: true }));
    if (goAhead) window.location.href = TRIPS_URL;
}

// ---------- public functions ----------

// Starts a search: shows the popup with "Looking for rides...", calls POST /quotes, then shows the options.
async function findRide(journey, labels = {}) {
    state.runId += 1;
    const run = state.runId;
    state.journey = journey;
    state.labels = labels || {};
    state.data = null;
    state.selected = null;
    state.keys = new Map();
    clearResults();
    renderTrip();
    openOverlay();
    showStep("results");
    showStatus("loading");
    try {
        const data = await apiRequest("/quotes", { method: "POST", body: journey });
        if (run !== state.runId || !state.open) return;
        state.data = data;
        clear($("rp-status"));
        renderResults();
    } catch (error) {
        if (run !== state.runId || !state.open) return;
        showStatus("error", error);
    }
}

// Shows options you already have (the answer of POST /quotes).
function open(response, labels = {}) {
    state.runId += 1;
    state.journey = null;
    state.labels = labels || {};
    state.data = response;
    state.selected = null;
    state.keys = new Map();
    renderTrip();
    openOverlay();
    showStep("results");
    renderResults();
}

// ---------- start-up: connect every button ----------

function init() {
    if (!$("rp-overlay")) {
        console.error("ride-popups: the popup markup (ride-popups.html) is not on this page");
        return;
    }
    $("rp-overlay").addEventListener("click", (event) => {
        if (event.target.closest("[data-rp-close]")) close();
    });
    $("rp-more-toggle").addEventListener("click", () => {
        const opening = $("rp-more").hidden;
        $("rp-more").hidden = !opening;
        $("rp-more-toggle").setAttribute("aria-expanded", String(opening));
        $("rp-more-toggle").textContent = opening ? "Hide other options" : "See all options";
    });
    $("rp-back").addEventListener("click", () => {
        if (!state.inFlight) showStep("results");
    });
    $("rp-confirm-check").addEventListener("change", updateConfirmState);
    $("rp-confirm").addEventListener("click", confirmBooking);
    $("rp-view-trips").addEventListener("click", goToTrips);

    document.addEventListener("keydown", (event) => {
        if (!state.open) return;
        if (event.key === "Escape") {
            close();
            return;
        }
        if (event.key === "Tab") {
            // keep the keyboard focus inside the popup
            const focusable = Array.from(
                $("rp-dialog").querySelectorAll("button, input, [tabindex='0']")
            ).filter((node) => !node.disabled && node.offsetParent !== null);
            if (focusable.length === 0) return;
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        }
    });
}

init();
window.RidePopup = { findRide, open, close };
export { findRide, open, close };
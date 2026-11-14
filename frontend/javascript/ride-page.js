// ride-page.js
// Only for ride.html.
// Job: run the custom provider dropdown, check the form, turn the typed places
// into map positions, show them on the map, and start the search. The results window (ride-popups.js)
// shows the answer and handles booking.
//
// Needs these scripts on the page, in this order:
//   leaflet.js (the map library), auth-config.js, auth.js, place-search.js (optional), ride-page.js,
//   then the two modules: api-client.js and ride-popups.js

// ---------- 1. SETTINGS ----------

// Used when the page has no field with the id "currency". Allowed: see ALLOWED_CURRENCIES.
const DEFAULT_CURRENCY = "EUR";
const ALLOWED_CURRENCIES = ["EUR", "GBP", "PLN", "USD", "CHF", "SEK", "NOK", "DKK", "CZK", "HUF"];

// The API knows providers by their id. If the values in the provider dropdown
// (the data-value in ride.html) are already these ids, this list can stay as it is.
const PROVIDER_IDS = { bolt: "mock-bolt", uber: "mock-uber", ecabs: "mock-ecabs" };

// The API refuses more than this.
const MAX_PASSENGERS = 8;
const MAX_BAGS = 6;

// Where the map starts (the middle of Malta) and how far it is zoomed in.
const MALTA_CENTRE = [35.9375, 14.3754];
const MALTA_ZOOM = 11;

// ---------- 2. PAGE ELEMENTS ----------

const rideForm = document.getElementById("rideForm");
const pickup = document.getElementById("pickup");
const dropoff = document.getElementById("dropoff");
const passengers = document.getElementById("passengers");
const provider = document.getElementById("provider"); // hidden input, holds the chosen value
const belongings = document.getElementById("belongings"); // the number of bags
const swapBtn = document.getElementById("swapBtn");
const formMsg = document.getElementById("formMsg");
const currencyField = document.getElementById("currency"); // optional
const submitBtn = rideForm ? rideForm.querySelector('[type="submit"]') : null;
const mapElement = document.getElementById("rideMap");

const fields = { pickup: pickup, dropoff: dropoff };

function showMessage(text, ok) {
    formMsg.textContent = text;
    formMsg.classList.toggle("ok", Boolean(ok));
}

function normalise(text) {
    return String(text).trim().replace(/\s+/g, " ").toLowerCase();
}

// ---------- 2B. MAP ----------
// Leaflet draws the map. The "L" object comes from leaflet.js.
// If the map element or the library is missing, the map is skipped
// and the rest of the page still works.

let map = null;
const markers = { pickup: null, dropoff: null }; // the pins on the map, or null

if (mapElement && typeof L !== "undefined") {
    map = L.map(mapElement).setView(MALTA_CENTRE, MALTA_ZOOM);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        referrerPolicy: "origin",
        attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
}

// Zoom so that all pins are visible.
function fitMap() {
    if (!map) return;
    const pins = [markers.pickup, markers.dropoff].filter(Boolean);
    if (pins.length === 0) {
        map.setView(MALTA_CENTRE, MALTA_ZOOM);
    } else if (pins.length === 1) {
        map.setView(pins[0].getLatLng(), 15);
    } else {
        map.fitBounds(L.latLngBounds(pins.map((pin) => pin.getLatLng())), { padding: [50, 50] });
    }
}

// Put a pin at the position. If the pin already exists, move it.
function showMarker(kind, position) {
    if (!map) return;
    const latLng = [position.lat, position.lon];
    if (markers[kind]) {
        markers[kind].setLatLng(latLng);
    } else {
        markers[kind] = L.marker(latLng).addTo(map);
        markers[kind].bindTooltip(kind === "pickup" ? "Pickup" : "Dropoff");
    }
    fitMap();
}

// Take the pin off the map.
function hideMarker(kind) {
    if (!map || !markers[kind]) return;
    map.removeLayer(markers[kind]);
    markers[kind] = null;
    fitMap();
}

// Draw the pins again from what is stored in "chosen" (used after a swap).
function redrawMarkers() {
    ["pickup", "dropoff"].forEach((kind) => {
        if (chosen[kind]) showMarker(kind, chosen[kind]);
        else hideMarker(kind);
    });
}

// ---------- 3. PLACES ----------
// Each field ends up as a position (lat and lon) in one of two ways:
//   a) the user picked a suggestion while typing: we already have the position
//   b) the user typed a full name: we ask the backend (OpenStreetMap) once

const chosen = { pickup: null, dropoff: null }; // { lat, lon, text } or null
const resolving = { pickup: null, dropoff: null }; // { asked, promise } while a search runs

class PlaceProblem extends Error { }

function readCoordinates(place) {
    if (!place) return null;
    const lat = Number(place.lat !== undefined ? place.lat : place.latitude);
    const lon = Number(place.lon !== undefined ? place.lon : place.lng !== undefined ? place.lng : place.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
    return { lat: lat, lon: lon };
}

// Called when the user picks a suggestion.
function remember(kind, place) {
    const coordinates = readCoordinates(place);
    if (!coordinates) {
        chosen[kind] = null;
        hideMarker(kind);
        return;
    }
    chosen[kind] = { lat: coordinates.lat, lon: coordinates.lon, text: null };
    showMarker(kind, coordinates);
    // The suggestion list writes its text into the field a moment later.
    setTimeout(() => {
        if (chosen[kind] && chosen[kind].text === null) chosen[kind].text = normalise(fields[kind].value);
    }, 0);
}

// If the user edits the text after picking a suggestion, the picked position is forgotten.
Object.keys(fields).forEach((kind) => {
    fields[kind].addEventListener("input", () => {
        const entry = chosen[kind];
        if (entry && entry.text !== null && entry.text !== normalise(fields[kind].value)) {
            chosen[kind] = null;
            hideMarker(kind);
        }
    });
});

async function searchByName(text) {
    if (!window.ApiClient) throw new PlaceProblem("The page is still loading. Please try again in a moment.");
    const answer = await window.ApiClient.apiRequest("/locations/search", {
        method: "POST",
        body: { query: text },
    });
    if (answer.status === "OK" && answer.place) return { lat: answer.place.lat, lon: answer.place.lon };
    if (answer.status === "OUTSIDE_MALTA") {
        throw new PlaceProblem('"' + text + '" is outside Malta. Please choose a place in Malta.');
    }
    if (answer.status === "NOT_FOUND") {
        throw new PlaceProblem('We could not find "' + text + '". Check the spelling or choose one of the suggestions.');
    }
    // UNAVAILABLE: the place search service is down. The list of common places will be offered here later.
    throw new PlaceProblem("Place search is not available right now. Please pick a place from the suggestions while typing, then try again.");
}

// Gives the position for one field. Never asks the backend twice for the same text.
function resolvePlace(kind) {
    const input = fields[kind];
    const asked = normalise(input.value);
    const entry = chosen[kind];
    if (entry && (entry.text === null || entry.text === asked)) {
        return Promise.resolve({ lat: entry.lat, lon: entry.lon });
    }
    if (resolving[kind] && resolving[kind].asked === asked) return resolving[kind].promise;

    const promise = searchByName(input.value.trim())
        .then((coordinates) => {
            // Keep the answer only if the user has not changed the text meanwhile.
            if (normalise(input.value) === asked) {
                chosen[kind] = { lat: coordinates.lat, lon: coordinates.lon, text: asked };
                showMarker(kind, coordinates);
            }
            return coordinates;
        })
        .finally(() => {
            if (resolving[kind] && resolving[kind].promise === promise) resolving[kind] = null;
        });
    resolving[kind] = { asked: asked, promise: promise };
    return promise;
}

function friendlyError(error) {
    if (error instanceof PlaceProblem) return error.message;
    if (error instanceof TypeError) return "We could not reach the service. Check your connection and try again.";
    return (error && error.message) || "Something went wrong. Please try again.";
}

// Suggestions while typing (needs place-search.js). If that script is not on the page,
// the typed names are still searched when the form is sent.
if (typeof PlaceSearch !== "undefined" && typeof PlaceSearch.attach === "function") {
    Object.keys(fields).forEach((kind) => {
        PlaceSearch.attach(fields[kind], {
            onSelect: (place) => remember(kind, place),
            onClear: () => {
                chosen[kind] = null;
                hideMarker(kind);
            },
            onEnter: () => {
                if (!fields[kind].value.trim()) return;
                resolvePlace(kind).catch((error) => showMessage(friendlyError(error), false));
            },
            onUnavailable: () => { },
        });
    });
}

// ---------- 4. SWAP ----------

if (swapBtn) {
    swapBtn.addEventListener("click", () => {
        const temp = pickup.value;
        pickup.value = dropoff.value;
        dropoff.value = temp;
        const tempPlace = chosen.pickup;
        chosen.pickup = chosen.dropoff;
        chosen.dropoff = tempPlace;
        resolving.pickup = null;
        resolving.dropoff = null;
        redrawMarkers();
    });
}

// ---------- 5. CUSTOM PROVIDER DROPDOWN ----------
// A button shows the chosen provider. A list opens under it.
// Mouse and keyboard both work (arrows, Enter, Space, Escape).

const providerSelect = document.getElementById("providerSelect");
const providerBtn = document.getElementById("providerBtn");
const providerLabel = document.getElementById("providerLabel");
const providerList = document.getElementById("providerList");

if (providerSelect && providerBtn && providerLabel && providerList && provider) {
    const options = Array.from(providerList.querySelectorAll('[role="option"]'));
    let activeIndex = 0;
    let swallowSpaceKeyup = false;

    function selectedIndex() {
        return options.findIndex((o) => o.getAttribute("aria-selected") === "true");
    }

    function setActive(index) {
        activeIndex = index;
        options.forEach((o, i) => o.classList.toggle("is-active", i === index));
        providerBtn.setAttribute("aria-activedescendant", options[index].id);
    }

    function setOpen(open) {
        providerList.hidden = !open;
        providerBtn.setAttribute("aria-expanded", String(open));
        providerSelect.dataset.open = String(open);
        if (open) setActive(Math.max(selectedIndex(), 0));
        else providerBtn.removeAttribute("aria-activedescendant");
    }

    function choose(index) {
        options.forEach((o, i) => o.setAttribute("aria-selected", String(i === index)));
        providerLabel.textContent = options[index].textContent;
        provider.value = options[index].dataset.value;
        setOpen(false);
        providerBtn.focus();
    }

    providerBtn.addEventListener("click", () => setOpen(providerList.hidden));

    providerBtn.addEventListener("keydown", (event) => {
        const isOpen = !providerList.hidden;

        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            if (!isOpen) {
                setOpen(true);
                return;
            }
            const step = event.key === "ArrowDown" ? 1 : -1;
            setActive((activeIndex + step + options.length) % options.length);
        } else if ((event.key === "Enter" || event.key === " ") && isOpen) {
            event.preventDefault();
            if (event.key === " ") swallowSpaceKeyup = true;
            choose(activeIndex);
        } else if (event.key === "Escape" && isOpen) {
            event.preventDefault();
            setOpen(false);
        } else if (event.key === "Tab" && isOpen) {
            setOpen(false);
        }
    });

    // Some browsers fire a click when Space is released. Stop that after choosing.
    providerBtn.addEventListener("keyup", (event) => {
        if (event.key === " " && swallowSpaceKeyup) {
            event.preventDefault();
            swallowSpaceKeyup = false;
        }
    });

    options.forEach((option, index) => {
        option.addEventListener("click", () => choose(index));
        option.addEventListener("mousemove", () => setActive(index));
    });

    document.addEventListener("click", (event) => {
        if (!providerSelect.contains(event.target)) setOpen(false);
    });
}

// ---------- 6. THE FORM ----------

// "any" (or nothing) means no preference. Otherwise the API needs the provider id.
function preferredProviderId() {
    const value = (provider.value || "").trim();
    if (!value || value.toLowerCase() === "any") return null;
    return PROVIDER_IDS[value.toLowerCase()] || value;
}

function setBusy(busy) {
    if (submitBtn) submitBtn.disabled = busy;
}

let searching = false;

if (rideForm) {
    rideForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (searching) return;

        const from = pickup.value.trim();
        const to = dropoff.value.trim();
        const count = Number(passengers.value);
        const bagsText = belongings.value.trim();
        const bags = bagsText === "" ? 0 : Number(bagsText);

        if (!from || !to) {
            showMessage("Please enter both pickup and dropoff locations.", false);
            return;
        }
        if (normalise(from) === normalise(to)) {
            showMessage("Pickup and dropoff cannot be the same place.", false);
            return;
        }
        if (!passengers.value.trim() || !Number.isInteger(count) || count < 1 || count > MAX_PASSENGERS) {
            showMessage("Please enter the number of passengers, as a whole number from 1 to " + MAX_PASSENGERS + ".", false);
            return;
        }
        if (!Number.isInteger(bags) || bags < 0 || bags > MAX_BAGS) {
            showMessage("Please enter the number of bags, as a whole number from 0 to " + MAX_BAGS + " (or leave it empty).", false);
            return;
        }
        if (!window.RidePopup) {
            showMessage("The results window is not ready yet. Please try again in a moment.", false);
            return;
        }

        searching = true;
        setBusy(true);
        showMessage("Checking the places...", true);
        try {
            const positions = await Promise.all([resolvePlace("pickup"), resolvePlace("dropoff")]);
            const start = positions[0];
            const end = positions[1];
            if (start.lat === end.lat && start.lon === end.lon) {
                showMessage("Pickup and dropoff cannot be the same place.", false);
                return;
            }

            // This is exactly what the API expects for POST /quotes.
            const journey = {
                pickup: { lat: start.lat, lon: start.lon },
                destination: { lat: end.lat, lon: end.lon },
                passengers: count,
                load: bags,
                currency: currencyChoice(),
            };
            const preferred = preferredProviderId();
            if (preferred) journey.preferredProvider = preferred;

            showMessage("", true);
            window.RidePopup.findRide(journey, { pickupLabel: from, destinationLabel: to });
        } catch (error) {
            showMessage(friendlyError(error), false);
        } finally {
            searching = false;
            setBusy(false);
        }
    });
}

function currencyChoice() {
    const value = currencyField ? String(currencyField.value).trim().toUpperCase() : DEFAULT_CURRENCY;
    return ALLOWED_CURRENCIES.includes(value) ? value : DEFAULT_CURRENCY;
}

// "Search again" in the results window, when there is nothing to repeat: back to the form.
document.addEventListener("ridepopup:searchagain", () => {
    if (pickup) pickup.focus();
});
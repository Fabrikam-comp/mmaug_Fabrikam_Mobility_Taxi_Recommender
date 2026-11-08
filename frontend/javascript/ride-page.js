// ride-page.js
// Only for ride.html.
// Job: run the custom provider dropdown, check the form, gather the answers
// into one request object, and (later) send it to the backend.
// The map is left for the backend.

// ---------- 1. SETTINGS (fill in when the backend is ready) ----------

// The address that receives the ride search, for example "https://your-api.example.com/rides/search".
const RIDES_API_URL = "";

// ---------- 2. PAGE ELEMENTS ----------

const rideForm = document.getElementById("rideForm");
const pickup = document.getElementById("pickup");
const dropoff = document.getElementById("dropoff");
const passengers = document.getElementById("passengers");
const provider = document.getElementById("provider"); // hidden input, holds the chosen value
const belongings = document.getElementById("belongings");
const swapBtn = document.getElementById("swapBtn");
const formMsg = document.getElementById("formMsg");

function showMessage(text, ok) {
    formMsg.textContent = text;
    formMsg.classList.toggle("ok", Boolean(ok));
}

// ---------- 3. SWAP ----------

if (swapBtn) {
    swapBtn.addEventListener("click", () => {
        const temp = pickup.value;
        pickup.value = dropoff.value;
        dropoff.value = temp;
    });
}

// ---------- 4. CUSTOM PROVIDER DROPDOWN ----------
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

// ---------- 5. SENDING THE SEARCH ----------

// Later, your backend decides what to send back (ride options, a route for the map, and so on).
// This function is the one place that will need to change.
async function sendSearch(request) {
    if (!RIDES_API_URL) {
        showMessage("Search is not connected to the backend yet.", false);
        return;
    }

    showMessage("Searching...", true);

    try {
        const response = await fetch(RIDES_API_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(request),
        });
        if (!response.ok) throw new Error("Server answered " + response.status);

        const data = await response.json();
        showMessage("", true);
        onSearchResult(data);
    } catch (error) {
        console.error("Ride search failed:", error);
        showMessage("We could not search for rides. Please try again.", false);
    }
}

// Called with whatever the backend returns. Draw the map and results here later.
function onSearchResult(data) {
    // intentionally empty for now
}

// ---------- 6. THE FORM ----------

if (rideForm) {
    rideForm.addEventListener("submit", (event) => {
        event.preventDefault();

        const from = pickup.value.trim();
        const to = dropoff.value.trim();
        const count = Number(passengers.value);

        if (!from || !to) {
            showMessage("Please enter both pickup and dropoff locations.", false);
            return;
        }
        if (from.toLowerCase() === to.toLowerCase()) {
            showMessage("Pickup and dropoff cannot be the same place.", false);
            return;
        }
        if (!passengers.value.trim() || !Number.isInteger(count) || count < 1) {
            showMessage("Please enter the number of passengers, as a whole number of 1 or more.", false);
            return;
        }

        // One object holding everything the user chose.
        const request = {
            pickup: from,
            dropoff: to,
            passengers: count,
            provider: provider.value, // "any" means no preference
            belongings: belongings.value.trim(), // may be empty
        };

        sendSearch(request);
    });
}
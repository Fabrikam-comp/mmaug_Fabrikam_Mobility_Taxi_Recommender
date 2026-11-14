// app-page.js
// Only for app.html (the logged-in page).
// Login and the real name menu are handled by auth.js and navbar.js.

const pickup = document.getElementById("pickup");
const dropoff = document.getElementById("dropoff");
const clearPickup = document.getElementById("clearPickup");
const swapBtn = document.getElementById("swapBtn");
const rideForm = document.getElementById("rideForm");
const formMsg = document.getElementById("formMsg");

// 1. Clear the pickup box
if (clearPickup) {
    clearPickup.addEventListener("click", () => {
        pickup.value = "";
        pickup.focus();
        formMsg.textContent = "";
    });
}

// 2. Swap pickup and dropoff
if (swapBtn) {
    swapBtn.addEventListener("click", () => {
        const temp = pickup.value;
        pickup.value = dropoff.value;
        dropoff.value = temp;
    });
}

// 3. Find a ride: check both boxes are filled
if (rideForm) {
    rideForm.addEventListener("submit", (event) => {
        event.preventDefault();
        const from = pickup.value.trim();
        const to = dropoff.value.trim();

        formMsg.classList.remove("ok");

        if (!from || !to) {
            formMsg.textContent = "Please enter both pickup and dropoff locations.";
            return;
        }
        if (from.toLowerCase() === to.toLowerCase()) {
            formMsg.textContent = "Pickup and dropoff cannot be the same place.";
            return;
        }

        window.location.href =
            "ride.html?pickup=" + encodeURIComponent(from) +
            "&dropoff=" + encodeURIComponent(to);
    });
}

// 4. Smooth scroll button (only runs if the button exists on this page)
const howBtn = document.getElementById("howBtn");
const howSection = document.getElementById("how");
if (howBtn && howSection) {
    howBtn.addEventListener("click", () => {
        howSection.scrollIntoView({ behavior: "smooth" });
    });
}

// 5. "How to request a ride" carousel (only runs if the section exists)
const track = document.getElementById("track");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");
const pageCount = document.getElementById("pageCount");

if (track && prevBtn && nextBtn && pageCount) {
    const totalPages = track.children.length;
    let currentPage = 0;

    function showPage(index) {
        currentPage = index;
        track.style.transform = `translateX(-${index * 100}%)`;
        pageCount.textContent = `${index + 1}/${totalPages}`;
        prevBtn.disabled = index === 0;
        nextBtn.disabled = index === totalPages - 1;
    }

    prevBtn.addEventListener("click", () => showPage(currentPage - 1));
    nextBtn.addEventListener("click", () => showPage(currentPage + 1));
    showPage(0);
}

// 6. Journey tabs (only runs if the tabs exist)
const tabs = document.querySelectorAll(".app-tab");
const panels = document.querySelectorAll("[data-panel]");

tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
        tabs.forEach((t) => {
            const active = t === tab;
            t.classList.toggle("active", active);
            t.setAttribute("aria-selected", String(active));
        });
        panels.forEach((panel) => {
            panel.hidden = panel.dataset.panel !== tab.dataset.tab;
        });
    });
});

// 7. Go buttons: put the place in the dropoff box and jump back to the form
document.querySelectorAll(".app-go").forEach((btn) => {
    btn.addEventListener("click", () => {
        dropoff.value = btn.dataset.place;
        formMsg.textContent = "";
        rideForm.scrollIntoView({ behavior: "smooth", block: "center" });
        if (!pickup.value.trim()) pickup.focus();
        else dropoff.focus();
    });
});


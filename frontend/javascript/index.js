// Grab the elements we need
const pickup = document.getElementById("pickup");
const dropoff = document.getElementById("dropoff");
const clearPickup = document.getElementById("clearPickup");
const swapBtn = document.getElementById("swapBtn");
const rideForm = document.getElementById("rideForm");
const formMsg = document.getElementById("formMsg");
const howBtn = document.getElementById("howBtn");
const cityName = document.getElementById("cityName");
const navLinks = document.querySelectorAll(".nav-links a");

// 1. Clear the pickup box
clearPickup.addEventListener("click", () => {
    pickup.value = "";
    pickup.focus();
    formMsg.textContent = "";
});

// 2. Swap pickup and dropoff
swapBtn.addEventListener("click", () => {
    const temp = pickup.value;
    pickup.value = dropoff.value;
    dropoff.value = temp;
});

// 3. See prices: check both boxes are filled
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

    formMsg.classList.add("ok");
    formMsg.textContent = `Looking for rides from ${from} to ${to}...`;
    // Later, this is where you would call your backend API.
});

// 4. Smooth scroll to the "How to request a ride" section
howBtn.addEventListener("click", () => {
    document.getElementById("how").scrollIntoView({ behavior: "smooth" });
});

// 6. Highlight the nav link you click
navLinks.forEach((link) => {
    link.addEventListener("click", () => {
        navLinks.forEach((l) => l.classList.remove("active"));
        link.classList.add("active");
    });
});

// 7. "How to request a ride" carousel (2 pages)
const track = document.getElementById("track");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");
const pageCount = document.getElementById("pageCount");
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
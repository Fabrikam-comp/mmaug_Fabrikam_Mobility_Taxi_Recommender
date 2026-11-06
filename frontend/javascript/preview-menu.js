// preview-menu.js
// TEMPORARY. Shows the name menu while you work on your own computer.
// It runs only on localhost or 127.0.0.1, and only when nobody is logged in.
// On the real website it does nothing.
// Load it after navbar.js on app.html, ride.html and trips.html.
// Delete this file (and its script tags) once real login works.
(async function () {
    const isLocal = ["localhost", "127.0.0.1"].includes(window.location.hostname);
    if (!isLocal) return;

    const account = await Auth.init();
    if (account) return; // a real login exists, navbar.js handles everything

    const userMenu = document.getElementById("userMenu");
    const userBtn = document.getElementById("userBtn");
    const userName = document.getElementById("userName");
    const userDropdown = document.getElementById("userDropdown");
    const signOutBtn = document.getElementById("signOutBtn");
    const welcome = document.getElementById("welcomeName");
    if (!userMenu || !userBtn || !userDropdown) return;

    userMenu.hidden = false;
    userName.textContent = "Preview User";
    if (welcome) welcome.textContent = "Preview User";

    function setMenu(open) {
        userDropdown.hidden = !open;
        userBtn.setAttribute("aria-expanded", String(open));
    }

    userBtn.addEventListener("click", (event) => {
        event.stopPropagation();
        setMenu(userDropdown.hidden);
    });
    document.addEventListener("click", (event) => {
        if (!userMenu.contains(event.target)) setMenu(false);
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") setMenu(false);
    });

    // There is no real session in preview mode, so just go to the home page.
    if (signOutBtn) {
        signOutBtn.addEventListener("click", () => {
            window.location.href = "index.html";
        });
    }
})();
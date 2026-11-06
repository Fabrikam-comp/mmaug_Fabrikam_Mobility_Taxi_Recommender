// header.js
// ONE shared header for every logged-in page (app.html, ride.html, trips.html).
// Each page only holds an empty spot: <div id="siteHeader"></div>
// This file builds the header and puts it there.
//
// To change the navbar, edit this file only.
// IMPORTANT: load it BEFORE navbar.js and preview-menu.js, because those two
// look for the name button and dropdown, and those exist only after this runs.

(function () {
    const mount = document.getElementById("siteHeader");
    if (!mount) return;

    // The main links. Change the order, names or addresses here.
    const NAV_LINKS = [
        { label: "Home", href: "app.html" },
        { label: "Ride", href: "ride.html" },
        { label: "About", href: "#" },
        { label: "Trips", href: "trips.html" },
        { label: "Help", href: "#" },
    ];

    // Which page are we on? "ride.html" and "ride" both become "ride".
    function pageName(path) {
        const last = path.split("/").pop().replace(/\.html$/, "");
        return last || "index";
    }
    const currentPage = pageName(window.location.pathname);

    const linksHtml = NAV_LINKS.map((link) => {
        const isActive = link.href !== "#" && pageName(link.href) === currentPage;
        const attrs = isActive ? ' class="active" aria-current="page"' : "";
        return '<a href="' + link.href + '"' + attrs + ">" + link.label + "</a>";
    }).join("\n                ");

    const headerHtml = `
    <header class="navbar">
        <div class="container nav-inner">
            <a href="index.html" class="logo">
                <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
                    <path fill="currentColor" fill-rule="evenodd"
                        d="M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zm0 9.5a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5z" />
                </svg>
                Fabrikam
            </a>

            <nav class="nav-links" aria-label="Main">
                ${linksHtml}
            </nav>

            <div class="nav-actions">
                <div class="user-menu" id="userMenu" hidden>
                    <button class="user-btn" id="userBtn" type="button" aria-haspopup="true" aria-expanded="false">
                        <svg class="user-avatar" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
                            <circle cx="12" cy="8" r="4" fill="currentColor" />
                            <path d="M4 20c0-4 3.6-6 8-6s8 2 8 6z" fill="currentColor" />
                        </svg>
                        <span id="userName">Account</span>
                        <svg class="chev" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
                            <path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"
                                stroke-linejoin="round" d="M6 9l6 6 6-6" />
                        </svg>
                    </button>
                    <div class="user-dropdown" id="userDropdown" hidden>
                        <a href="trips.html" class="user-item">Trips</a>
                        <a href="#" class="user-item">Manage account</a>
                        <button class="user-item user-signout" id="signOutBtn" type="button">Sign out</button>
                    </div>
                </div>
            </div>
        </div>
    </header>`;

    // Swap the empty spot for the real header (no extra wrapper left behind).
    const template = document.createElement("template");
    template.innerHTML = headerHtml.trim();
    mount.replaceWith(template.content);
})();
// mobile-menu.js
// Phone menu in the Uber style. Works on any page that has a ".navbar" with
// ".nav-links" and ".nav-actions", so the same file serves index.html and the
// logged-in pages.
//
// It adds a hamburger button at the end of the bar. Tapping it opens a
// full-width panel under the bar. The panel copies the links from ".nav-links",
// so you only ever edit the links in one place.
//
// Load order on logged-in pages: header.js first, then this file.
// On index.html, load it with the other scripts at the bottom.

(function () {
    const header = document.querySelector(".navbar");
    if (!header) return;

    const links = header.querySelector(".nav-links");
    const actions = header.querySelector(".nav-actions");
    if (!links || !actions) return;

    // The phone breakpoint. Keep it the same as the CSS media query.
    const desktopQuery = window.matchMedia("(min-width: 861px)");

    // ---------- the hamburger button ----------
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "menu-toggle";
    toggle.setAttribute("aria-label", "Open menu");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-controls", "mobilePanel");
    toggle.innerHTML =
        '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" ' +
        'stroke-width="2" stroke-linecap="round" aria-hidden="true">' +
        '<path class="icon-open" d="M4 7h16M4 12h16M4 17h16" />' +
        '<path class="icon-close" d="M6 6l12 12M18 6L6 18" />' +
        "</svg>";
    actions.appendChild(toggle);

    // ---------- the panel ----------
    const panel = document.createElement("nav");
    panel.id = "mobilePanel";
    panel.className = "mobile-panel";
    panel.setAttribute("aria-label", "Mobile");
    panel.hidden = true;

    links.querySelectorAll("a").forEach((link) => {
        panel.appendChild(link.cloneNode(true));
    });
    header.appendChild(panel);

    // ---------- open and close ----------
    function setOpen(open) {
        panel.hidden = !open;
        toggle.setAttribute("aria-expanded", String(open));
        toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
        document.body.classList.toggle("menu-open", open);

        if (open) {
            // The panel fills the screen below the bar, so it needs the bar's height.
            document.documentElement.style.setProperty("--nav-h", header.offsetHeight + "px");
        }
    }

    toggle.addEventListener("click", () => setOpen(panel.hidden));

    // Tapping a link closes the menu.
    panel.addEventListener("click", (event) => {
        if (event.target.closest("a")) setOpen(false);
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !panel.hidden) {
            setOpen(false);
            toggle.focus();
        }
    });

    // If the window becomes wide (for example a phone turned sideways), close it.
    desktopQuery.addEventListener("change", (event) => {
        if (event.matches) setOpen(false);
    });
})();
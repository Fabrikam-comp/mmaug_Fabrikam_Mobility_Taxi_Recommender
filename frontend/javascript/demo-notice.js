/* demo-notice.js
 *
 * One shared demo notice for app.html and index.html. It is put at the very top of
 * the hero section, above the welcome line.
 * Change the wording or the repo address here and nowhere else.
 * Styles: the DEMO NOTICE block at the end of css/style.css.
 */
(function () {
    "use strict";

    var NOTICE_TEXT = `MMAUG-Taxi-Recommender is a solution built as part of the malta Microsoft AI user Group(MMAUG) AI & DevOps Fundamentals Bootcamp 2026. The solution is for demo/educational purpose and not to be adopted as a producyion ready system`
    var REPO_URL = "https://github.com/Fabrikam-comp/mmaug_Fabrikam_Mobility_Taxi_Recommender";
    var LINK_TEXT = "Check-Repo";

    function addNotice() {
        // app.html uses .app-hero, index.html uses .hero. If neither is found, do nothing.
        var hero = document.querySelector(".app-hero, .hero");
        if (!hero || hero.querySelector(".demo-notice")) {
            return;
        }

        var row = document.createElement("div");
        row.className = "demo-notice-row";

        var box = document.createElement("div");
        box.className = "demo-notice";
        box.setAttribute("role", "note");

        var text = document.createElement("span");
        text.textContent = NOTICE_TEXT;

        var link = document.createElement("a");
        link.href = REPO_URL;
        link.textContent = LINK_TEXT;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.setAttribute("aria-label", "Check the project repository on GitHub (opens in a new tab)");

        box.append(text, link);
        row.appendChild(box);
        hero.prepend(row);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", addNotice);
    } else {
        addNotice();
    }
})();
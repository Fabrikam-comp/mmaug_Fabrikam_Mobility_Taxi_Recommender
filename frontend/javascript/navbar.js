// Runs on every page that has the navbar (index.html, app.html).
// Logged out: shows Log in / Sign up. Logged in: shows the name menu.
(async function () {
    const loginBtn = document.getElementById("loginBtn");
    const signupBtn = document.getElementById("signupBtn");
    const accountIcon = document.getElementById("accountIcon");
    const userMenu = document.getElementById("userMenu");
    const userBtn = document.getElementById("userBtn");
    const userName = document.getElementById("userName");
    const userDropdown = document.getElementById("userDropdown");
    const signOutBtn = document.getElementById("signOutBtn");

    if (loginBtn) {
        loginBtn.addEventListener("click", () => {
            window.location.href = "login.html";
        });
    }
    if (signupBtn) {
        signupBtn.addEventListener("click", () => {
            window.location.href = "signup.html";
        });
    }

    const account = await Auth.init();

    if (!account) {
        // Pages marked data-protected send logged-out visitors to the login page.
        // This is only a convenience. Real protection is the API checking the token.
        if (document.body.hasAttribute("data-protected")) {
            window.location.replace("login.html");
        }
        return;
    }

    const name = Auth.getDisplayName(account);

    // Swap the logged-out buttons for the name menu.
    if (loginBtn) loginBtn.hidden = true;
    if (signupBtn) signupBtn.hidden = true;
    if (accountIcon) accountIcon.hidden = true;
    if (userMenu) userMenu.hidden = false;
    if (userName) userName.textContent = name;

    const welcome = document.getElementById("welcomeName");
    if (welcome) welcome.textContent = name;

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
    signOutBtn.addEventListener("click", () => Auth.signOut());
})();
// Shared login code (uses MSAL.js, Microsoft's login library).
// Every page that needs login loads this file.
const Auth = (() => {
    let msalInstance = null;
    let readyPromise = null;

    // What we ask Microsoft for. Add the API scope here later.
    const loginRequest = { scopes: ["openid", "profile"] };

    // Returns a message if something is not set up yet, otherwise null.
    function setupProblem() {
        if (typeof msal === "undefined") {
            return "The MSAL file is missing. Add msal-browser.min.js to javascript/vendor.";
        }
        if (
            typeof AUTH_CONFIG === "undefined" ||
            AUTH_CONFIG.clientId.startsWith("PASTE") ||
            AUTH_CONFIG.tenantSubdomain.startsWith("PASTE")
        ) {
            return "Login is not set up yet. Add the Client ID and tenant subdomain in auth-config.js.";
        }
        return null;
    }

    // Builds a full address for a page that sits next to the current page.
    function pageUrl(file) {
        return new URL(file, window.location.href).href;
    }

    function getAccount() {
        if (!msalInstance) return null;
        let account = msalInstance.getActiveAccount();
        if (!account) {
            const all = msalInstance.getAllAccounts();
            if (all.length > 0) {
                account = all[0];
                msalInstance.setActiveAccount(account);
            }
        }
        return account;
    }

    async function start() {
        if (setupProblem()) return null;

        msalInstance = new msal.PublicClientApplication({
            auth: {
                clientId: AUTH_CONFIG.clientId,
                authority: "https://" + AUTH_CONFIG.tenantSubdomain + ".ciamlogin.com/",
                redirectUri: pageUrl("app.html"),
                postLogoutRedirectUri: pageUrl("index.html"),
            },
            cache: { cacheLocation: "sessionStorage" },
        });

        await msalInstance.initialize();

        // Finishes the login when Microsoft sends the user back to our site.
        try {
            const result = await msalInstance.handleRedirectPromise();
            if (result && result.account) msalInstance.setActiveAccount(result.account);
        } catch (error) {
            console.error("Login did not finish:", error);
        }

        return getAccount();
    }

    return {
        // Safe to call many times. Resolves to the signed-in account, or null.
        init() {
            if (!readyPromise) readyPromise = start();
            return readyPromise;
        },
        setupProblem,
        signIn() {
            return msalInstance.loginRedirect({ ...loginRequest });
        },
        // "create" asks Microsoft to open the sign-up page first.
        signUp() {
            return msalInstance.loginRedirect({ ...loginRequest, prompt: "create" });
        },
        signOut() {
            return msalInstance.logoutRedirect({ account: getAccount() });
        },
        getDisplayName(account) {
            return (
                account.name ||
                (account.idTokenClaims && account.idTokenClaims.name) ||
                account.username ||
                "Account"
            );
        },
    };
})();
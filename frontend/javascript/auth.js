// auth.js
// Shared login code (uses MSAL.js, Microsoft's login library).
// Every page that needs login loads this file.
const Auth = (() => {
    let msalInstance = null;
    let readyPromise = null;

    // What we ask Microsoft for at login. The API token is requested later.
    const loginRequest = { scopes: ["openid", "profile"] };

    function isLocal() {
        const host = window.location.hostname;
        return host === "localhost" || host === "127.0.0.1";
    }

    // The addresses saved in Azure. Which ones we use depends on where the page runs.
    function redirectAddresses() {
        const saved = AUTH_CONFIG.redirectUri;
        if (isLocal()) {
            return { login: saved.local, home: saved.local };
        }
        return { login: saved.production.login, home: saved.production.home };
    }

    function isPlaceholder(value) {
        return typeof value !== "string" || value === "" || value.startsWith("PASTE");
    }

    // Returns a message if something is not set up yet, otherwise null.
    function setupProblem() {
        if (typeof msal === "undefined") {
            return "The MSAL file is missing. Add msal-browser.min.js to javascript/vendor.";
        }
        if (typeof AUTH_CONFIG === "undefined") {
            return "Login is not set up yet. Check auth-config.js.";
        }
        if (isPlaceholder(AUTH_CONFIG.clientId) || isPlaceholder(AUTH_CONFIG.tenantId)) {
            return "Login is not set up yet. Add the Client ID and Tenant ID in auth-config.js.";
        }
        if (isLocal() && isPlaceholder(AUTH_CONFIG.redirectUri && AUTH_CONFIG.redirectUri.local)) {
            return "Local testing needs the local redirect address in auth-config.js.";
        }
        return null;
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

        const addresses = redirectAddresses();

        msalInstance = new msal.PublicClientApplication({
            auth: {
                clientId: AUTH_CONFIG.clientId,
                authority: "https://login.microsoftonline.com/" + AUTH_CONFIG.tenantId,
                redirectUri: addresses.login,
                postLogoutRedirectUri: addresses.home,
            },
            cache: { cacheLocation: "sessionStorage" },
        });

        await msalInstance.initialize();

        // Finishes the login when Microsoft sends the user back to our site.
        // false = do not jump back to the page where login started, finish it here.
        try {
            const result = await msalInstance.handleRedirectPromise({
                navigateToLoginRequestUrl: false,
            });
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
        // Same as signIn. Microsoft shows its sign-up experience to new guests
        // only if the admin linked a self-service sign-up flow to the app.
        signUp() {
            return msalInstance.loginRedirect({ ...loginRequest });
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
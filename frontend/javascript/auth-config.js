const AUTH_CONFIG = {
    // Application (client) ID of the app registration
    clientId: "PASTE_CLIENT_ID_HERE",

    // Directory (tenant) ID
    tenantId: "PASTE_TENANT_ID_HERE",

    // Optional. Leave empty and the code builds the API scope from the client ID.
    // Only fill this in if that default does not work.
    apiScope: "",

    // Backend API address, with no slash at the end
    apiBaseUrl: "PASTE_BACKEND_API_URL_HERE",

    // Where Microsoft sends the user back after login and after sign out.
    // Must match the addresses saved in Azure exactly.
    redirectUri: {
        production: {
            // Where the user lands after signing out (the home page)
            home: "https://yellow-hill-0648c4e03.6.azurestaticapps.net",
            // Where Microsoft sends the user back after login
            login: "https://yellow-hill-0648c4e03.6.azurestaticapps.net/login",
        },
        // Used only when the page runs on localhost.
        // Paste the saved address exactly, including any path.
        local: "http://localhost:5500",
    },
};
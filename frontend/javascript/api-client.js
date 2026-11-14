/* API client: the one place that talks to the backend.
   - adds the API address (AUTH_CONFIG.apiBaseUrl) and "Authorization: Bearer <ID token>"
   - gets a fresh ID token from Auth.getIdToken() (see auth-add-getIdToken.js)
   - on a 401 it refreshes the token and tries once more, then sends the user to login
   - turns every API error into an ApiError with: status, code, message, details, retryAfter
   Tokens are never logged or stored here. */

const LOGIN_URL = "login.html"; // where to send the user when the session cannot be renewed
const TIMEOUT_MS = 30000; // the Free plan app can be slow to wake up

export class ApiError extends Error {
    constructor({ status = 0, code = "ERROR", message = "Something went wrong.", details = null, retryAfter = null }) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.code = code;
        this.details = details;
        this.retryAfter = retryAfter;
    }
}

let redirecting = false;

function goToLogin() {
    if (redirecting) return;
    redirecting = true;
    window.location.href = LOGIN_URL;
}

function baseUrl() {
    const base = typeof AUTH_CONFIG !== "undefined" ? String(AUTH_CONFIG.apiBaseUrl || "") : "";
    if (!base || base.includes("PASTE_")) {
        throw new ApiError({ code: "API_NOT_CONFIGURED", message: "The API address is not set in auth-config.js." });
    }
    return base.replace(/\/+$/, "");
}

async function getToken(forceRefresh) {
    if (typeof Auth === "undefined" || typeof Auth.getIdToken !== "function") {
        throw new ApiError({ code: "AUTH_NOT_READY", message: "Sign-in is not ready on this page." });
    }
    const token = await Auth.getIdToken(forceRefresh);
    if (!token) {
        goToLogin();
        throw new ApiError({ status: 401, code: "NOT_SIGNED_IN", message: "Please sign in to continue." });
    }
    return token;
}

async function send(url, options, token) {
    const headers = { Accept: "application/json", ...(options.headers || {}), Authorization: "Bearer " + token };
    const init = { method: options.method || "GET", headers, credentials: "omit", cache: "no-store" };
    if (options.body !== undefined) {
        headers["Content-Type"] = "application/json";
        init.body = JSON.stringify(options.body);
    }
    const controller = new AbortController();
    init.signal = controller.signal;
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    try {
        return await fetch(url, init);
    } catch (error) {
        if (error && error.name === "AbortError") {
            throw new ApiError({ code: "TIMEOUT", message: "The service took too long to answer. Please try again." });
        }
        throw error; // a network failure (TypeError): the pages show a "check your connection" message
    } finally {
        clearTimeout(timer);
    }
}

async function readBody(response) {
    const text = await response.text();
    if (!text) return null;
    try {
        return JSON.parse(text);
    } catch (error) {
        return null;
    }
}

function toApiError(response, body) {
    const detail = body && body.detail !== undefined ? body.detail : null;
    const retry = Number(response.headers.get("Retry-After"));
    const error = { status: response.status, retryAfter: retry > 0 ? retry : null };
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
        // our own errors: { code, message, ...extra }
        return new ApiError({ ...error, code: detail.code || "ERROR", message: detail.message || "Something went wrong.", details: detail });
    }
    if (Array.isArray(detail)) {
        // the API refused the data it was sent (validation)
        return new ApiError({ ...error, code: "VALIDATION_ERROR", message: "Some of the details are not valid. Please check them and try again.", details: { code: "VALIDATION_ERROR", errors: detail } });
    }
    return new ApiError({ ...error, code: response.status === 401 ? "UNAUTHORIZED" : "ERROR", message: typeof detail === "string" ? detail : "Something went wrong." });
}

export async function apiRequest(path, options = {}) {
    const url = baseUrl() + path;
    let response = await send(url, options, await getToken(false));
    if (response.status === 401) {
        // The token may just have expired: get a fresh one and try once more.
        response = await send(url, options, await getToken(true));
        if (response.status === 401) {
            goToLogin();
            throw new ApiError({ status: 401, code: "SESSION_ENDED", message: "Your session has ended. Please sign in again." });
        }
    }
    const body = await readBody(response);
    if (!response.ok) throw toApiError(response, body);
    return body;
}

// For pages that use ordinary (non-module) scripts, such as ride-page.js and trips-page.js.
window.ApiClient = { apiRequest, ApiError };
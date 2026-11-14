# Fabrikam Taxi Recommender

> A web app that compares ride options from several taxi providers in Malta and recommends one, with a explanation.

This is a training simulation built for the MMAUG AI & DevOps Bootcamp (Group 4). The customer, Fabrikam Mobility Ltd is fictitious. **Prices are simulated. Nothing is charged and no driver is sent.**

**Live site:** <[link to the Azure Static Web App](https://yellow-hill-0648c4e03.6.azurestaticapps.net/)>

---

## Table of contents

1. [About the project](#about-the-project)
2. [Features](#features)
3. [Tech stack](#tech-stack)
4. [Project structure](#project-structure)
5. [Getting started](#getting-started)
6. [Configuration](#configuration)
7. [Running the tests](#running-the-tests)
8. [Deployment](#deployment)
9. [API overview](#api-overview)
10. [Security notes](#security-notes)
11. [Team](#team)
12. [License](#license)

---

## About the project

Mobility providers use different APIs, login methods and answer formats, Fabrikam Mobility wants visitors and residents in Malta to enter a pickup point and a destination and get transport recommendations, without the app being tied to one provider.

This app:

- collects ride options from several provider integrations and turns them into one common format,
- recommends one option and explains why,
- keeps working when one provider is slow, failing, rate limited or unavailable,
- lets new providers be added later without a major rewrite.

Provider facts (prices, availability, journey estimates) come only from provider or test data. AI is used only for the explanation text, never to invent facts.

## Features

- Compare quotes from several providers (Bolt, Uber and eCabs, all simulated by mock services).
- Ranked recommendation with an explanation. A plain template text is used when AI is switched off.
- Place search by name (OpenStreetMap) with suggestions while typing (Geoapify).
- Map with pickup and dropoff pins (Leaflet).
- Simulated booking that needs the user's clear confirmation.
- Trip history for signed-in users, stored in Azure Cosmos DB.
- Sign in with a Microsoft account (Microsoft Entra ID, using MSAL).
- Chatbot on the site (Foundry agent).
- Graceful handling of provider timeouts, errors, rate limits and missing prices.

## Tech stack

| Part | Technology |
| --- | --- |
| Frontend | HTML, CSS, JavaScript|
| Backend API | Python, <framework: fastapi |
| Database | Azure Cosmos DB |
| Authentication | Microsoft Entra ID, tokens checked by the API |
| Place search | OpenStreetMap geocoding, Geoapify suggestions |
| AI | Foundry |
| Hosting | Azure Static Web Apps (frontend), Azure Web App running a Docker container |
| Container registry | GitHub Container Registry |
| CI/CD | GitHub Actions, passwordless Azure login (OIDC) |
| Package tool | uv |

## Project structure

```text
bootcamp_project/
├── .github/
│   └── workflows/
│       ├── Ci.yml
│       └── Deploy.yml
├── api/
│   ├── adapters/
│   │   ├── base.py
│   │   ├── bolt.py
│   │   ├── ecabs.py
│   │   ├── httpclient.py
│   │   ├── registry.py
│   │   └── uber.py
│   ├── auth/
│   │   ├── dependencies.py
│   │   ├── token_check.py
│   │   └── user_id.py
│   ├── cache/
│   │   ├── coalescing.py
│   │   └── ttl_cache.py
│   ├── core/
│   │   ├── booking_service.py
│   │   ├── circuit_breaker.py
│   │   ├── models.py
│   │   ├── quote_service.py
│   │   ├── quote_set_store.py
│   │   └── quote_store.py
│   ├── currency/
│   │   ├── converter.py
│   │   └── rates_client.py
│   ├── data/
│   │   ├── cosmos_client.py
│   │   └── repositories.py
│   ├── explain/
│   │   ├── fact_sheet.py
│   │   ├── model_chain.py
│   │   ├── service.py
│   │   ├── template.py
│   │   └── validator.py
│   ├── locations/
│   │   ├── fallback_places.py
│   │   ├── geocoder.py
│   │   ├── landmark_name.py
│   │   └── malta_bounds.py
│   ├── routes/
│   │   ├── bookings.py
│   │   ├── common.py
│   │   ├── explanations.py
│   │   ├── locations.py
│   │   ├── quotes.py
│   │   └── trips.py
│   ├── scoring/
│   │   ├── fit.py
│   │   └── ranking.py
│   ├── config.py
│   ├── Dockerfile
│   ├── main.py
│   ├── services.py
│   └── wiring.py
├── frontend/
│   ├── css/
│   │   ├── auth.css
│   │   ├── place-search.css
│   │   ├── ride-popups.css
│   │   └── style.css
│   ├── images/
│   │   ├── airport.jpg
│   │   ├── city.jpg
│   │   ├── get-matched.jpg
│   │   ├── get-started.jpg
│   │   └── meet-your-driver.jpg
│   ├── javascript/
│   │   ├── vendor/
│   │   │   └── msal-browser.min.js
│   │   ├── api-client.js
│   │   ├── app-page.js
│   │   ├── auth-config.js
│   │   ├── auth-page.js
│   │   ├── auth.js
│   │   ├── chat-bot.js
│   │   ├── header.js
│   │   ├── index.js
│   │   ├── mobile-menu.js
│   │   ├── navbar.js
│   │   ├── place-search.js
│   │   ├── preview-menu.js
│   │   ├── ride-page.js
│   │   ├── ride-popups.js
│   │   └── trips-page.js
│   ├── app.html
│   ├── index.html
│   ├── login.html
│   ├── ride-popups.html
│   ├── ride.html
│   ├── signup.html
│   ├── staticwebapp.config.json
│   └── trips.html
├── mocks/
│   ├── bolt.py
│   ├── ecabs.py
│   ├── fault_switch.py
│   ├── main.py
│   ├── settings.py
│   ├── simulation.py
│   └── uber.py
├── scripts/
│   └── dev.ps1
├── tests/
│   └── test_health.py
├── .dockerignore
├── .env
├── .gitignore
├── .python-version
├── build_fallback_places.py
├── env.example
├── fallback_places_draft.txt
├── LICENSE
├── pyproject.toml
├── pytest.ini
├── README.md
├── st.md
└── uv.lock
```

## Getting started

### Prerequisites

- Python
- [uv]
- An Azure Cosmos DB account (the app stores trips there)

### 1. Clone the repository

```bash
git clone https://github.com/Fabrikam-comp/mmaug_Fabrikam_Mobility_Taxi_Recommender.git
cd bootcamp_project
```

### 2. Set up the environment variables

Windows:

```bash
copy env.example .env
```

Mac or Linux:

```bash
cp env.example .env
```

Then fill in the lines marked `TODO` in `.env`:

- `USER_ID_HMAC_KEY`: make your own random value:

```bash
uv run python -c "import secrets; print(secrets.token_hex(32))"
```

- `COSMOS_ENDPOINT` and `COSMOS_KEY`: from the Keys page of your Cosmos DB account in the Azure portal.
- `GEOCODER_CONTACT`: your own email.
- `GEOAPIFY_API_KEY`: From Geoaplify.

`.env` must never be committed.

### 3. Install dependencies

```bash
uv sync
```

### 4. Start the API

The mock providers run inside the API, so there is no separate mock step.


```bash
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Check it works: open `http://localhost:8000/health`.

### 5. Start the frontend

1. Open `frontend/javascript/auth-config.js` and replace the placeholders `PASTE_CLIENT_ID_HERE`, `PASTE_TENANT_ID_HERE`, `PASTE_BACKEND_API_URL_HERE` and, if you use suggestions, `PASTE_GEOAPIFY_KEY_HERE`. Do not commit these values. The deploy pipeline fills them in for production.
2. Serve the `frontend/` folder on port 5500 and open `frontend/app.html`.

## Configuration

Settings are read from `.env` locally. In production the Deploy workflow copies them from GitHub secrets and variables into the web app's settings.

| Variable | What it does |
| --- | --- |
| `AUTH_MODE` | Login check mode. Must be `token` in production. |
| `AUTH_ACCEPT_ID_TOKEN` | Accept Microsoft ID tokens . |
| `AUTH_ACCEPT_ACCESS_TOKEN` | Accept access tokens (`false` in this project). If `true`, `AUTH_REQUIRED_SCOPE` is needed. |
| `AUTH_REQUIRED_SCOPE`, `AUTH_API_AUDIENCE` | Optional token checks. |
| `AZURE_AD_TENANTID`, `AZURE_AD_CLIENTID` | Microsoft Entra tenant and app registration. |
| `USER_ID_HMAC_KEY` | Secret key used to create user IDs. Keep it private. |
| `COSMOS_ENDPOINT`, `COSMOS_KEY` | Cosmos DB address and key. If the key is empty, the API tries its managed identity. |
| `COSMOS_DATABASE`, `COSMOS_CONTAINER_TRIPS` | Database and container names (`fabrikam` and `trips` locally). |
| `GEOCODER_CONTACT` | Your contact, sent to OpenStreetMap in the User-Agent. |
| `GEOAPIFY_API_KEY` | Optional. Turns on suggestions while typing. |
| `BOLT_CLIENT_ID`, `BOLT_CLIENT_SECRET`, `UBER_SERVER_TOKEN`, `ECABS_API_KEY` | Provider credentials. Locally these are made-up values for the mocks. An empty value switches that provider off. |
| `BOLT_BASE_URL`, `UBER_BASE_URL`, `ECABS_BASE_URL` | Provider addresses. Default to the built-in mocks. |
| `ADAPTERS_ENABLED`, `ADAPTER_TIMEOUT_S` | Which providers are on, and how long to wait for them. |
| `MOCK_ADMIN_KEY` | Key for the fault switch of the mocks. Empty keeps it closed. |
| `CORS_ORIGIN` | The website address allowed to call the API (production). |
| `AI_ENABLED`, `AI_TIMEOUT_S`, `AI_DAILY_CAP_FOUNDRY`, `AI_DAILY_CAP_GITHUB` | Optional AI explanations and their daily limits. |
| `FOUNDRY_ENDPOINT`, `FOUNDRY_API_KEY`, `FOUNDRY_DEPLOYMENT_NAME` | Foundry settings for AI explanations. |
| `GH_MODELS_TOKEN`, `GH_MODELS_MODEL` | GitHub Models settings (stored as `GITHUB_MODELS_*` in the web app). |
| `FOUNDRY_AGENT_RESPONSES_URL`, `CHAT_DAILY_CAP`, `CHAT_TIMEOUT_S` | Chatbot settings. |

## Running the tests

```bash
uv run pytest
```

<Confirm this command works, and describe what Ci.yml runs.>

## Deployment

Deployment runs from `.github/workflows/Deploy.yml` on every push to main branch. It uses the prod environment, and never runs two deploys at once. It first works out what changed, so a frontend-only change does not restart the API.

**API (Azure Web App, Docker container)**

1. Build the image and test it on the build machine before anything is pushed: check every module imports, start the container, check `/health` answers, and check that `/trips` refuses a call without a token (401).
2. Push the image to GitHub Container Registry.
3. Log in to Azure without a password (OIDC).
4. Check that required settings exist, then copy GitHub secrets and variables into the web app settings.
5. Deploy the image, make sure the app is running, then check `/health`.
6. If the API is not healthy, stop the web app to protect the free plan quota.

**Frontend (Azure Static Web Apps)**

1. Replace the placeholders in `auth-config.js` on the build machine only.
2. Upload the `frontend/` folder. There is no build step. The frontend is not deployed if the API deploy failed.

**GitHub settings needed**

| Type | Names |
| --- | --- |
| Variables | `AZURE_WEBAPP_NAME`, `AZURE_RESOURCE_GROUP`, `CORS_ORIGIN`, `BACKEND_API_URL` |
| Secrets (Azure login) | `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_STATIC_WEB_APPS_API_TOKEN` |
| Secrets (app) | `USER_ID_HMAC_KEY`, `AZURE_AD_TENANTID`, `AZURE_AD_CLIENTID`, `COSMOS_ENDPOINT`, `COSMOS_KEY` |
| Optional | `GEOAPIFY_API_KEY`, `GEOCODER_CONTACT`, provider credentials, and the AI and chatbot settings above |


## API overview

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/health` | Health check |
| POST | `/locations/search` | Turns a place name into coordinates (Malta only) |
| POST | `/quotes` | Gets ride quotes for a journey |
| GET | `/trips` | Trip history (needs a sign-in token) |

The mock providers are served by the same app under `/mocks`.

## Security notes

- Real secrets live in GitHub secrets and Azure settings, never in the repository.
- `.env` is listed in `.gitignore`.
- The local provider credentials are made-up values for the mocks.
- Production requires `AUTH_MODE=token`. Protected routes refuse calls without a token.
- Azure login from GitHub uses OIDC.
- Simulated data is always labelled as simulated.

## Team
Group D

## License
See the [LICENSE](LICENSE) file.

## Acknowledgements
- Organised by the Malta Microsoft Azure User Group (MMAUG)
import os

# Websites that are allowed to call this API from a browser (CORS allow-list).
# These addresses are public, so they are safe to keep in the repo.
DEFAULT_ORIGINS = [
    "https://yellow-hill-0648c4e03.6.azurestaticapps.net",  # the one frontend
    "http://localhost:5500",  # Live Server
    "http://127.0.0.1:5500",  # Live Server (other spelling)
]


def get_allowed_origins() -> list[str]:
    """Use the CORS_ORIGINS app setting if it exists (comma separated),
    otherwise use the default list above."""
    raw = os.getenv("CORS_ORIGINS")
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return DEFAULT_ORIGINS

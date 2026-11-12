"""The mock providers app. Run it on its own:

    uv run uvicorn mocks.main:app --port 9000 --reload

It has no imports from api/, so it can also be mounted inside another app.
"""

from fastapi import FastAPI

from mocks import bolt, ecabs, fault_switch, uber


def create_app() -> FastAPI:
    app = FastAPI(title="Fabrikam mock taxi providers (SIMULATED)")

    @app.get("/health")
    def health():
        return {"status": "okay"}

    app.include_router(bolt.router)
    app.include_router(uber.router)
    app.include_router(ecabs.router)
    app.include_router(fault_switch.admin_router)
    return app


app = create_app()

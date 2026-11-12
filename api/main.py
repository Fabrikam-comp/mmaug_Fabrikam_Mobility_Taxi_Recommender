from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.wiring import include_routes, lifespan
from config import get_allowed_origins
from mocks.main import app as mocks_app

app = FastAPI(title="Fabrikam Taxi Recommender API", lifespan=lifespan)
include_routes(app)
app.mount("/mocks", mocks_app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)


@app.get("/health")
def get_health():
    return {"status": "okay"}

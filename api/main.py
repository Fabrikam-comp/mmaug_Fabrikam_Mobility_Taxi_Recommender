from fastapi import FastAPI

app = FastAPI(title="Fabrikam Taxi Recommender API")


@app.get("/health")
def get_health():
    return {"status": "okay"}

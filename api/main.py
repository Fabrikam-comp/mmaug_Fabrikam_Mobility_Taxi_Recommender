from fastapi.middleware.cors import CORSMiddleware
from api.wiring import include_routes, lifespan
from api.config import get_allowed_origins
from mocks.main import app as mocks_app
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from api.chat.agent import (
    AgentUnavailable,
    ChatReply,
    ChatRequest,
    client_key,
    close_agent_chat,
    get_agent_chat,
)


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    async with lifespan(app):
        try:
            yield
        finally:
            await close_agent_chat()

app = FastAPI(title="Fabrikam Taxi Recommender API", lifespan=app_lifespan)
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


@app.post("/chat", response_model=ChatReply)
async def post_chat(body: ChatRequest, request: Request):
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail={
                            "code": "EMPTY_MESSAGE", "message": "Please type a message."})
    chat = get_agent_chat()
    if chat is None:
        raise HTTPException(status_code=503, detail={
                            "code": "CHAT_OFF", "message": "The assistant is not available right now."})
    caller = client_key(request.headers.get(
        "x-forwarded-for", ""), request.client.host if request.client else None)
    wait = chat.limiter.check(caller)
    if wait is not None:
        raise HTTPException(status_code=429, detail={
                            "code": "TOO_MANY_MESSAGES", "message": "Please wait a moment before sending another message."}, headers={"Retry-After": str(wait)})
    try:
        return ChatReply(reply=await chat.ask(message, body.sessionId))
    except AgentUnavailable:
        raise HTTPException(status_code=503, detail={
                            "code": "CHAT_UNAVAILABLE", "message": "The assistant could not answer. Please try again."})

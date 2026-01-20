from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .event_broker import EventBroker
from .session_manager import SessionManager
from .session_runner import RunConfig, SessionRunner


app = FastAPI(title="Computer Use Demo API")
session_manager = SessionManager(Path(__file__).resolve().parent / "data" / "sessions.db")
event_broker = EventBroker()
session_runner = SessionRunner(session_manager, event_broker)
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),
    name="static",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/sessions")
def create_session() -> dict[str, str]:
    session = session_manager.create()
    return {"id": session.id, "created_at": session.created_at.isoformat()}


@app.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, str]:
    session = session_manager.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"id": session.id, "created_at": session.created_at.isoformat()}


class MessageIn(BaseModel):
    role: str
    content: str


class EventIn(BaseModel):
    message: str


class RunIn(BaseModel):
    model: str
    provider: str = "anthropic"
    system_prompt_suffix: str = ""
    max_tokens: int = 4096
    tool_version: str = "computer_use_20251124"
    thinking_budget: int | None = None
    token_efficient_tools_beta: bool = False
    only_n_most_recent_images: int | None = None


# Add a message to session.
@app.post("/sessions/{session_id}/messages")
def add_message(session_id: str, message: MessageIn) -> dict[str, str]:
    session = session_manager.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    session_manager.add_message(session_id, message.role, message.content)
    return {"status": "ok"}


# Get messages from session.
@app.get("/sessions/{session_id}/messages")
def list_messages(session_id: str) -> list[dict[str, str]]:
    session = session_manager.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return session_manager.list_messages(session_id)


@app.get("/sessions/{session_id}/events")
async def stream_events(session_id: str, request: Request) -> StreamingResponse:
    session = session_manager.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    async def event_generator():
        async for message in event_broker.subscribe(session_id):
            if await request.is_disconnected():
                break
            yield f"data: {message}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/sessions/{session_id}/events")
async def publish_event(session_id: str, event: EventIn) -> dict[str, str]:
    session = session_manager.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    await event_broker.publish(session_id, event.message)
    return {"status": "ok"}


@app.post("/sessions/{session_id}/run")
async def run_session(session_id: str, run: RunIn) -> dict[str, str]:
    session = session_manager.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    try:
        config = RunConfig(
            model=run.model,
            provider=run.provider,
            system_prompt_suffix=run.system_prompt_suffix,
            max_tokens=run.max_tokens,
            tool_version=run.tool_version,  # type: ignore[arg-type]
            thinking_budget=run.thinking_budget,
            token_efficient_tools_beta=run.token_efficient_tools_beta,
            only_n_most_recent_images=run.only_n_most_recent_images,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    started = await session_runner.start(session_id, config)
    if not started:
        raise HTTPException(status_code=409, detail="session already running")
    return {"status": "started"}

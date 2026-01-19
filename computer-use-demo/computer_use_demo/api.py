from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .event_broker import EventBroker
from .session_manager import SessionManager


app = FastAPI(title="Computer Use Demo API")
session_manager = SessionManager(Path(__file__).resolve().parent / "data" / "sessions.db")
event_broker = EventBroker()


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

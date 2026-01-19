from pathlib import Path

from fastapi import FastAPI, HTTPException

from .session_manager import SessionManager


app = FastAPI(title="Computer Use Demo API")
session_manager = SessionManager(Path(__file__).resolve().parent / "data" / "sessions.db")


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

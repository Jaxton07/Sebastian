from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sebastian.gateway.auth import create_access_token, require_auth, verify_password

router = APIRouter(tags=["turns"])


class LoginRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SendTurnRequest(BaseModel):
    message: str
    session_id: str | None = None


class TurnResponse(BaseModel):
    session_id: str
    response: str
    ts: str


@router.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    from sebastian.config import settings
    stored_hash = settings.sebastian_owner_password_hash
    if not stored_hash or not verify_password(body.password, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid password")
    token = create_access_token({"sub": settings.sebastian_owner_name, "role": "owner"})
    return TokenResponse(access_token=token)


@router.post("/turns", response_model=TurnResponse)
async def send_turn(
    body: SendTurnRequest,
    _auth: dict = Depends(require_auth),
) -> TurnResponse:
    import sebastian.gateway.state as state
    session_id = body.session_id or str(uuid.uuid4())
    response = await state.sebastian.chat(body.message, session_id)
    return TurnResponse(
        session_id=session_id,
        response=response,
        ts=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/turns/{session_id}")
async def get_turns(
    session_id: str,
    _auth: dict = Depends(require_auth),
) -> dict:
    import sebastian.gateway.state as state
    async with state.session_factory() as session:
        from sebastian.memory.episodic_memory import EpisodicMemory
        episodic = EpisodicMemory(session)
        turns = await episodic.get_turns(session_id, limit=100)
    return {
        "session_id": session_id,
        "turns": [
            {"role": t.role, "content": t.content, "ts": t.created_at.isoformat()}
            for t in turns
        ],
    }

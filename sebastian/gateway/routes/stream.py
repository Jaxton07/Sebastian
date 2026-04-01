from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sebastian.gateway.auth import require_auth

router = APIRouter(tags=["stream"])


@router.get("/stream")
async def global_stream(
    request: Request,
    _auth: dict = Depends(require_auth),
) -> StreamingResponse:
    """SSE endpoint: streams all events to the connected client."""
    import sebastian.gateway.state as state

    async def event_generator():
        async for chunk in state.sse_manager.stream():
            if await request.is_disconnected():
                break
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

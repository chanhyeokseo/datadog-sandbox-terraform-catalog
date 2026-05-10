import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Query
from starlette.responses import StreamingResponse

from app.services.audit_service import audit_service
from app.services.event_bus import event_bus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/logs")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    return audit_service.get_entries(
        page=page,
        per_page=per_page,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/summary")
async def get_audit_summary():
    return audit_service.get_summary()


async def _sse_generator(queue: asyncio.Queue):
    try:
        yield "event: connected\ndata: {}\n\n"
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {payload}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        event_bus.unsubscribe(queue)


@router.get("/events")
async def audit_event_stream():
    queue = event_bus.subscribe()
    return StreamingResponse(
        _sse_generator(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

import asyncio
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.middleware.guardrails import MCP_SOURCE_HEADER, MCP_SOURCE_VALUE
from app.services.audit_service import (
    AuditEntry,
    audit_service,
    resolve_action,
    extract_resource,
    is_mutating,
)
from app.services.event_bus import event_bus

logger = logging.getLogger(__name__)

ACTOR_HEADER = "x-dogstac-actor"
SKIP_PREFIXES = ("/api/audit/", "/health", "/assets/")
STREAM_WRITE_ACTIONS = {
    "terraform.apply", "terraform.destroy", "terraform.init",
    "danger_zone.destroy_all",
}


def _is_mcp_request(request: Request) -> bool:
    return request.headers.get(MCP_SOURCE_HEADER, "").lower() == MCP_SOURCE_VALUE


def _should_skip(path: str) -> bool:
    return any(path.startswith(p) for p in SKIP_PREFIXES)


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if _should_skip(path) or not path.startswith("/api/"):
            return await call_next(request)

        mcp = _is_mcp_request(request)
        tool_action = resolve_action(request.method, path.rstrip("/"))

        is_write = is_mutating(tool_action) and (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            or tool_action in STREAM_WRITE_ACTIONS
        )
        if not mcp and not is_write:
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        clean_path = path.rstrip("/")
        method = request.method
        actor = request.headers.get(ACTOR_HEADER, "mcp-client") if mcp else "Web UI"
        resource = extract_resource(clean_path)
        status = "success" if response.status_code < 400 else "failed"

        entry = AuditEntry(
            actor=actor,
            tool_action=tool_action,
            resource=resource,
            status=status,
            duration_ms=elapsed_ms,
            method=method,
            path=clean_path,
            status_code=response.status_code,
        )

        audit_service.add_entry(entry)
        event_bus.publish("audit_entry", entry.to_dict())

        if is_mutating(tool_action) and status == "success":
            event_bus.publish("resource_changed", {
                "action": tool_action,
                "resource": resource,
            })

        asyncio.create_task(audit_service.persist_entry(entry))

        return response

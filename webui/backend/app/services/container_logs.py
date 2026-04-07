import asyncio
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TAIL = 500
MAX_TAIL = 5000
MAX_BYTES = 512_000


def _resolve_container_id() -> str | None:
    override = os.environ.get("DOCKER_LOGS_CONTAINER", "").strip()
    if override:
        return override
    try:
        return Path("/etc/hostname").read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _resolve_tail(requested: int) -> int:
    env = os.environ.get("DOCKER_LOGS_TAIL", "").strip()
    if env.isdigit():
        n = int(env)
    else:
        n = requested
    return max(1, min(n, MAX_TAIL))


async def fetch_docker_logs_tail(lines: int = DEFAULT_TAIL) -> tuple[bool, str]:
    container = _resolve_container_id()
    if not container:
        return False, "Could not resolve container id (set DOCKER_LOGS_CONTAINER or ensure /etc/hostname exists)"
    tail = _resolve_tail(lines)
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "logs",
            "--tail",
            str(tail),
            container,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=90)
        text = out.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            logger.debug("docker logs rc=%s len=%s", proc.returncode, len(text))
            return False, text.strip() or f"docker logs exited with code {proc.returncode}"
        raw = text.encode("utf-8")
        if len(raw) > MAX_BYTES:
            text = raw[:MAX_BYTES].decode("utf-8", errors="ignore") + "\n... [truncated]\n"
        return True, text
    except FileNotFoundError:
        return False, "docker CLI not found in container"
    except asyncio.TimeoutError:
        return False, "docker logs timed out"
    except Exception as e:
        logger.debug("fetch_docker_logs_tail failed: %s", e)
        return False, str(e)

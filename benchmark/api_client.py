import logging
import time

import httpx

from .config import BACKEND_URL

logger = logging.getLogger(__name__)

STREAM_TIMEOUT = 1800.0
TF_EXIT_SIGNAL = "__TF_EXIT__"


class TerraformAPI:
    def __init__(self):
        self._base = BACKEND_URL

    def init(self, resource_id: str) -> dict:
        return self._stream(f"/api/terraform/init/stream/{resource_id}")

    def plan(self, resource_id: str) -> dict:
        return self._stream(f"/api/terraform/plan/stream/{resource_id}")

    def apply(self, resource_id: str) -> dict:
        return self._stream(f"/api/terraform/apply/stream/{resource_id}?auto_approve=true")

    def destroy(self, resource_id: str) -> dict:
        return self._stream(f"/api/terraform/destroy/stream/{resource_id}?auto_approve=true")

    def output(self, resource_id: str) -> dict:
        start = time.time()
        with httpx.Client(timeout=60) as client:
            resp = client.get(f"{self._base}/api/terraform/output", params={"resource_id": resource_id})
            resp.raise_for_status()
        elapsed = time.time() - start
        return {"action": "output", "elapsed_sec": round(elapsed, 2), "exit_code": 0}

    def _stream(self, path: str) -> dict:
        url = f"{self._base}{path}"
        start = time.time()
        exit_code = -1
        output_size = 0

        logger.debug("SSE stream: %s", url)
        with httpx.Client(timeout=httpx.Timeout(STREAM_TIMEOUT, connect=10)) as client:
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    output_size += len(line)
                    if TF_EXIT_SIGNAL in line:
                        try:
                            exit_code = int(line.split(TF_EXIT_SIGNAL + ":")[1].strip())
                        except (IndexError, ValueError):
                            exit_code = -1
                        break

        elapsed = time.time() - start
        action = path.split("/stream/")[0].rsplit("/", 1)[-1] if "/stream/" in path else "unknown"
        result = {
            "action": action,
            "elapsed_sec": round(elapsed, 2),
            "exit_code": exit_code,
            "output_bytes": output_size,
        }
        logger.info("%s completed: %.1fs (exit=%d)", action, elapsed, exit_code)
        return result

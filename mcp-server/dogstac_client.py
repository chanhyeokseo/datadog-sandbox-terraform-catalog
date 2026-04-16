import os
import time
import logging
import httpx

logger = logging.getLogger(__name__)

DOGSTAC_API_URL = os.environ.get("DOGSTAC_API_URL", "http://localhost:7621")
MCP_HEADERS = {"X-DogSTAC-Source": "mcp"}
STREAM_TIMEOUT = 1800.0
_CRED_CACHE_TTL = 300
_CRED_CHECK_PATH = "/api/terraform/credentials/check"
_CRED_PATH_PREFIX = "/api/terraform/credentials/"
_CRED_EXPIRED_MSG = (
    "AWS SSO credentials are expired or not configured. "
    "Please call the sso_login tool to authenticate before retrying."
)
_BACKEND_NOT_READY_MSG = (
    "Backend is still initializing after SSO login (rebuilding S3 cache, "
    "refreshing presets). Please wait a moment and retry."
)


class CredentialsExpiredError(Exception):
    pass


class BackendNotReadyError(Exception):
    pass


class DogSTACClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or DOGSTAC_API_URL).rstrip("/")
        self._cred_valid_until: float = 0.0

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def invalidate_credential_cache(self) -> None:
        self._cred_valid_until = 0.0

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code == 401:
            self._cred_valid_until = 0.0
            raise CredentialsExpiredError(_CRED_EXPIRED_MSG)
        if resp.status_code == 403:
            detail = ""
            try:
                detail = resp.json().get("detail", "")
            except Exception:
                pass
            raise httpx.HTTPStatusError(
                f"403 Forbidden (guardrail): {detail}" if detail else "403 Forbidden",
                request=resp.request,
                response=resp,
            )
        resp.raise_for_status()

    async def _ensure_credentials(self, path: str) -> None:
        if path.startswith(_CRED_PATH_PREFIX):
            return
        now = time.monotonic()
        if now < self._cred_valid_until:
            return
        logger.debug("Pre-checking AWS credentials before request to %s", path)
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                resp = await c.get(
                    self._url(_CRED_CHECK_PATH), headers=MCP_HEADERS
                )
                if resp.status_code == 401 or not resp.json().get("valid"):
                    self._cred_valid_until = 0.0
                    raise CredentialsExpiredError(_CRED_EXPIRED_MSG)
                if not resp.json().get("initialized", True):
                    raise BackendNotReadyError(_BACKEND_NOT_READY_MSG)
                self._cred_valid_until = now + _CRED_CACHE_TTL
                logger.debug("Credentials valid and initialized, cached for %ds", _CRED_CACHE_TTL)
        except (CredentialsExpiredError, BackendNotReadyError):
            raise
        except Exception as e:
            logger.debug("Credential pre-check failed (non-auth): %s", e)

    async def get(self, path: str, **params) -> dict:
        await self._ensure_credentials(path)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(self._url(path), headers=MCP_HEADERS, params=params)
            self._raise_for_status(resp)
            return resp.json()

    async def put(self, path: str, json_body: dict) -> dict:
        await self._ensure_credentials(path)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.put(self._url(path), headers=MCP_HEADERS, json=json_body)
            self._raise_for_status(resp)
            return resp.json()

    async def post(self, path: str, json_body: dict | None = None) -> dict:
        await self._ensure_credentials(path)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self._url(path), headers=MCP_HEADERS, json=json_body)
            self._raise_for_status(resp)
            return resp.json()

    async def consume_stream(self, method: str, path: str, **kwargs) -> dict:
        await self._ensure_credentials(path)
        timeout = httpx.Timeout(STREAM_TIMEOUT, connect=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            output_lines: list[str] = []
            exit_code = -1
            async with client.stream(
                method, self._url(path), headers=MCP_HEADERS, **kwargs
            ) as response:
                self._raise_for_status(response)
                async for line in response.aiter_lines():
                    if line.startswith("__TF_EXIT__:"):
                        try:
                            exit_code = int(line.split(":")[1])
                        except (IndexError, ValueError):
                            exit_code = 1
                    else:
                        output_lines.append(line)
            return {
                "success": exit_code == 0,
                "exit_code": exit_code,
                "output": "\n".join(output_lines),
            }

    async def delete(self, path: str) -> dict:
        await self._ensure_credentials(path)
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.delete(self._url(path), headers=MCP_HEADERS)
            self._raise_for_status(resp)
            return resp.json()

    async def stream_get(self, path: str, **params) -> dict:
        return await self.consume_stream("GET", path, params=params)

    async def stream_post(self, path: str, json_body: dict | None = None, params: dict | None = None) -> dict:
        return await self.consume_stream("POST", path, json=json_body, params=params)

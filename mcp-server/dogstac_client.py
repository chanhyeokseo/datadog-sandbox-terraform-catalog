import os
import logging
import httpx

logger = logging.getLogger(__name__)

DOGSTAC_API_URL = os.environ.get("DOGSTAC_API_URL", "http://localhost:8000")
MCP_HEADERS = {"X-DogSTAC-Source": "mcp"}
STREAM_TIMEOUT = 1800.0


class DogSTACClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or DOGSTAC_API_URL).rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    async def get(self, path: str, **params) -> dict:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(self._url(path), headers=MCP_HEADERS, params=params)
            resp.raise_for_status()
            return resp.json()

    async def put(self, path: str, json_body: dict) -> dict:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.put(self._url(path), headers=MCP_HEADERS, json=json_body)
            resp.raise_for_status()
            return resp.json()

    async def post(self, path: str, json_body: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self._url(path), headers=MCP_HEADERS, json=json_body)
            resp.raise_for_status()
            return resp.json()

    async def consume_stream(self, method: str, path: str, **kwargs) -> dict:
        timeout = httpx.Timeout(STREAM_TIMEOUT, connect=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            output_lines: list[str] = []
            exit_code = -1
            async with client.stream(
                method, self._url(path), headers=MCP_HEADERS, **kwargs
            ) as response:
                response.raise_for_status()
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
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.delete(self._url(path), headers=MCP_HEADERS)
            resp.raise_for_status()
            return resp.json()

    async def stream_get(self, path: str, **params) -> dict:
        return await self.consume_stream("GET", path, params=params)

    async def stream_post(self, path: str, json_body: dict | None = None, params: dict | None = None) -> dict:
        return await self.consume_stream("POST", path, json=json_body, params=params)

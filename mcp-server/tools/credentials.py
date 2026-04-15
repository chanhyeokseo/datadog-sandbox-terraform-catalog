import json
import asyncio
import logging
import webbrowser
from mcp.server.fastmcp import FastMCP
from dogstac_client import DogSTACClient

logger = logging.getLogger(__name__)


def register(mcp: FastMCP, client: DogSTACClient):
    @mcp.tool()
    async def check_credentials() -> str:
        """Check if AWS credentials are valid. Call this when any operation fails with an authentication error."""
        try:
            data = await client.get("/api/terraform/credentials/check")
            return json.dumps(data, indent=2)
        except Exception as e:
            error_text = str(e)
            if "401" in error_text:
                return json.dumps({
                    "valid": False,
                    "message": "AWS credentials are expired or not configured. Use sso_login to authenticate.",
                }, indent=2)
            return json.dumps({"valid": False, "error": error_text}, indent=2)

    @mcp.tool()
    async def sso_login() -> str:
        """Start AWS SSO login. Opens the verification URL in the user's browser
        automatically and waits for approval (up to 5 minutes)."""
        data = await client.post("/api/terraform/credentials/sso-login")
        session_id = data.get("session_id")
        verification_uri = data.get("verification_uri", "")

        if verification_uri:
            try:
                webbrowser.open(verification_uri)
                logger.info("Opened SSO verification URL in browser: %s", verification_uri)
            except Exception as e:
                logger.warning("Failed to open browser: %s", e)

        for _ in range(60):
            poll = await client.get(f"/api/terraform/credentials/sso-status/{session_id}")
            status = poll.get("status", "")
            if status == "complete":
                return await _wait_backend_ready(client)
            if status not in ("pending", "authorization_pending"):
                return json.dumps({
                    "status": status,
                    "message": f"SSO login ended with status: {status}",
                    "details": poll,
                }, indent=2)
            await asyncio.sleep(5)

        return json.dumps({
            "status": "timeout",
            "message": "SSO login timed out after 5 minutes.",
        }, indent=2)


async def _wait_backend_ready(client: DogSTACClient, retries: int = 12, interval: float = 5) -> str:
    for attempt in range(retries):
        try:
            data = await client.get("/api/terraform/credentials/check")
            if data.get("valid"):
                logger.info("Backend ready after SSO login (attempt %d)", attempt + 1)
                return json.dumps({
                    "status": "complete",
                    "message": "SSO login successful. AWS credentials are now active.",
                }, indent=2)
        except Exception as e:
            logger.debug("Backend not ready yet (attempt %d): %s", attempt + 1, e)
        await asyncio.sleep(interval)
    return json.dumps({
        "status": "complete",
        "message": "SSO login successful but backend initialization may still be in progress.",
    }, indent=2)

import asyncio
import json
import logging
from mcp.server.fastmcp import FastMCP
from dogstac_client import DogSTACClient, CredentialsExpiredError

logger = logging.getLogger(__name__)


def register(mcp: FastMCP, client: DogSTACClient):
    @mcp.tool()
    async def check_credentials() -> str:
        """Check if AWS credentials are valid. Call this when any operation fails with an authentication error."""
        try:
            data = await client.get("/api/terraform/credentials/check")
            return json.dumps(data, indent=2)
        except CredentialsExpiredError:
            return json.dumps({
                "valid": False,
                "message": "AWS credentials are expired or not configured. Use sso_login to authenticate.",
            }, indent=2)
        except Exception as e:
            return json.dumps({"valid": False, "error": str(e)}, indent=2)

    @mcp.tool()
    async def sso_login(session_id: str = "") -> str:
        """AWS SSO login. Two modes:
        - No session_id: Start SSO login, returns verification URL, user code, and session_id.
          Present the URL and code to the user, then call again with session_id.
        - With session_id: Poll for completion (up to 5 min). Returns only after
          authentication AND backend initialization are complete."""
        if not session_id:
            data = await client.post("/api/terraform/credentials/sso-login")
            return json.dumps({
                "session_id": data.get("session_id"),
                "verification_uri": data.get("verification_uri", ""),
                "user_code": data.get("user_code"),
                "instruction": (
                    "Present the verification URL and user code to the user. "
                    "Ask the user to open the URL, enter the code, and approve. "
                    "Then call sso_login again with the session_id."
                ),
            }, indent=2)

        for _ in range(60):
            poll = await client.get(f"/api/terraform/credentials/sso-status/{session_id}")
            status = poll.get("status", "")
            if status == "complete":
                client.invalidate_credential_cache()
                return json.dumps({
                    "status": "complete",
                    "message": "SSO login successful. AWS credentials are active and backend is ready.",
                }, indent=2)
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

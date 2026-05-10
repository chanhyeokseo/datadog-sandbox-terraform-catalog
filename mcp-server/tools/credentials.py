import asyncio
import json
import logging
from mcp.server.fastmcp import FastMCP, Context
from dogstac_client import DogSTACClient, CredentialsExpiredError, set_actor, _actor_name

logger = logging.getLogger(__name__)


def _detect_actor(ctx: Context) -> None:
    if _actor_name:
        return
    try:
        info = ctx.session.client_params.clientInfo
        if info and info.name:
            set_actor(info.name)
    except Exception as e:
        logger.debug("Could not detect MCP client name: %s", e)


def register(mcp: FastMCP, client: DogSTACClient):
    @mcp.tool()
    async def check_credentials(ctx: Context) -> str:
        """Check if AWS credentials are valid. Call this when any operation fails with an authentication error."""
        _detect_actor(ctx)
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
          You MUST open the verification_uri in the user's browser by running
          `open <verification_uri>` via shell, then IMMEDIATELY call sso_login again
          with the returned session_id to start polling. Do NOT wait for user confirmation.
        - With session_id: Poll for completion (up to 5 min). Returns only after
          authentication AND backend initialization are complete."""
        if not session_id:
            data = await client.post("/api/terraform/credentials/sso-login")
            return json.dumps({
                "session_id": data.get("session_id"),
                "verification_uri": data.get("verification_uri", ""),
                "user_code": data.get("user_code"),
                "instruction": (
                    "1. Run `open <verification_uri>` via shell to open the URL in the browser. "
                    "2. Show the verification URL and user code to the user as fallback. "
                    "3. IMMEDIATELY call sso_login again with the session_id to start polling. "
                    "Do NOT wait for the user to confirm completion; the polling call will block "
                    "until authentication finishes automatically."
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

import json
import asyncio
from mcp.server.fastmcp import FastMCP
from dogstac_client import DogSTACClient


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
    async def sso_login(session_id: str = "") -> str:
        """Start AWS SSO login flow or poll for completion.

        Two modes:
        - No session_id: Start a new SSO login. Returns verification URL, user code, and session_id.
          Present the URL and code to the user, then call again with the session_id.
        - With session_id: Poll for login completion (up to 5 minutes).
        """
        if not session_id:
            data = await client.post("/api/terraform/credentials/sso-login")
            return json.dumps({
                "session_id": data.get("session_id"),
                "verification_uri": data.get("verification_uri"),
                "user_code": data.get("user_code"),
                "expires_in": data.get("expires_in"),
                "instruction": (
                    "Present the verification URL and user code to the user. "
                    "They must open the URL in a browser and enter the code to authenticate. "
                    "Then call sso_login again with the session_id to wait for completion."
                ),
            }, indent=2)

        for _ in range(60):
            data = await client.get(f"/api/terraform/credentials/sso-status/{session_id}")
            status = data.get("status", "")
            if status == "complete":
                return json.dumps({
                    "status": "complete",
                    "message": "SSO login successful. AWS credentials are now active.",
                }, indent=2)
            if status not in ("pending", "authorization_pending"):
                return json.dumps({
                    "status": status,
                    "message": f"SSO login ended with status: {status}",
                    "details": data,
                }, indent=2)
            await asyncio.sleep(5)

        return json.dumps({
            "status": "timeout",
            "message": "SSO login timed out after 5 minutes. Ask the user to try again.",
        }, indent=2)

import json
import pytest
from mcp.server.fastmcp import FastMCP

from dogstac_client import CredentialsExpiredError
from tools.credentials import register


@pytest.fixture
def mcp_with_tools(mock_client):
    mcp = FastMCP("test")
    register(mcp, mock_client)
    return mcp, mock_client


class TestCheckCredentials:

    async def test_valid_credentials(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"valid": True, "account": "123456789012", "arn": "arn:aws:iam::user"}
        tool = mcp._tool_manager._tools["check_credentials"]
        result = json.loads(await tool.run({}))
        assert result["valid"] is True
        assert result["account"] == "123456789012"

    async def test_expired_credentials(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.side_effect = CredentialsExpiredError("expired")
        tool = mcp._tool_manager._tools["check_credentials"]
        result = json.loads(await tool.run({}))
        assert result["valid"] is False
        assert "sso_login" in result["message"]


class TestSSOLogin:

    async def test_returns_verification_info(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.post.return_value = {
            "session_id": "sess-123",
            "verification_uri": "https://device.sso.ap-northeast-2.amazonaws.com/",
            "user_code": "ABCD-EFGH",
            "expires_in": 600,
        }
        tool = mcp._tool_manager._tools["sso_login"]
        result = json.loads(await tool.run({}))
        assert result["session_id"] == "sess-123"
        assert result["user_code"] == "ABCD-EFGH"
        assert "verification_uri" in result
        assert "instruction" in result


class TestPollSSOStatus:

    async def test_complete_and_initialized(self, mcp_with_tools):
        mcp, client = mcp_with_tools

        async def mock_get(path, **kwargs):
            if "sso-status" in path:
                return {"status": "complete"}
            return {"valid": True, "initialized": True}

        client.get = mock_get
        tool = mcp._tool_manager._tools["poll_sso_status"]
        result = json.loads(await tool.run({"session_id": "sess-123"}))
        assert result["status"] == "complete"
        assert "successful" in result["message"].lower()

    async def test_complete_but_not_initialized(self, mcp_with_tools):
        mcp, client = mcp_with_tools

        async def mock_get(path, **kwargs):
            if "sso-status" in path:
                return {"status": "complete"}
            return {"valid": True, "initialized": False}

        client.get = mock_get
        tool = mcp._tool_manager._tools["poll_sso_status"]
        result = json.loads(await tool.run({"session_id": "sess-123"}))
        assert result["status"] == "initializing"
        assert "initializing" in result["message"].lower()

    async def test_pending_returns_immediately(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"status": "pending"}
        tool = mcp._tool_manager._tools["poll_sso_status"]
        result = json.loads(await tool.run({"session_id": "sess-123"}))
        assert result["status"] == "pending"
        assert "pending" in result["message"].lower()

    async def test_session_consumed_but_still_initializing(self, mcp_with_tools):
        mcp, client = mcp_with_tools

        async def mock_get(path, **kwargs):
            if "sso-status" in path:
                return {"status": "expired", "message": "Session not found"}
            return {"valid": True, "initialized": False}

        client.get = mock_get
        tool = mcp._tool_manager._tools["poll_sso_status"]
        result = json.loads(await tool.run({"session_id": "sess-123"}))
        assert result["status"] == "initializing"

    async def test_session_consumed_and_ready(self, mcp_with_tools):
        mcp, client = mcp_with_tools

        async def mock_get(path, **kwargs):
            if "sso-status" in path:
                return {"status": "expired", "message": "Session not found"}
            return {"valid": True, "initialized": True}

        client.get = mock_get
        tool = mcp._tool_manager._tools["poll_sso_status"]
        result = json.loads(await tool.run({"session_id": "sess-123"}))
        assert result["status"] == "complete"

    async def test_truly_expired_status(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"status": "expired", "message": "Token expired"}
        tool = mcp._tool_manager._tools["poll_sso_status"]
        result = json.loads(await tool.run({"session_id": "sess-123"}))
        assert result["status"] == "expired"

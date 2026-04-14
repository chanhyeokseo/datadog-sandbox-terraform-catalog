import json
import pytest
from unittest.mock import AsyncMock
from mcp.server.fastmcp import FastMCP

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
        client.get.side_effect = Exception("401 Unauthorized")
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

    async def test_immediate_complete(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"status": "complete"}
        tool = mcp._tool_manager._tools["poll_sso_status"]
        result = json.loads(await tool.run({"session_id": "sess-123"}))
        assert result["status"] == "complete"
        assert "successful" in result["message"].lower()

    async def test_pending_then_complete(self, mcp_with_tools, monkeypatch):
        mcp, client = mcp_with_tools
        import tools.credentials as cred_mod
        monkeypatch.setattr(cred_mod.asyncio, "sleep", AsyncMock())

        call_count = 0
        async def mock_get(path, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return {"status": "pending"}
            return {"status": "complete"}

        client.get = mock_get
        tool = mcp._tool_manager._tools["poll_sso_status"]
        result = json.loads(await tool.run({"session_id": "sess-123"}))
        assert result["status"] == "complete"
        assert call_count == 3

    async def test_unexpected_status(self, mcp_with_tools, monkeypatch):
        mcp, client = mcp_with_tools
        import tools.credentials as cred_mod
        monkeypatch.setattr(cred_mod.asyncio, "sleep", AsyncMock())
        client.get.return_value = {"status": "expired"}
        tool = mcp._tool_manager._tools["poll_sso_status"]
        result = json.loads(await tool.run({"session_id": "sess-123"}))
        assert result["status"] == "expired"

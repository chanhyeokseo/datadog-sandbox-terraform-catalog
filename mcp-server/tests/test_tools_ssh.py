import json
import pytest
from mcp.server.fastmcp import FastMCP

from tools.ec2_ssh import register


@pytest.fixture
def mcp_with_tools(mock_client):
    mcp = FastMCP("test")
    register(mcp, mock_client)
    return mcp, mock_client


class TestSSHExecuteTool:

    async def test_returns_command_result(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.post.return_value = {
            "stdout": "active (running)\n",
            "stderr": "",
            "exit_code": 0,
            "hostname": "10.0.0.1",
        }
        tool = mcp._tool_manager._tools["ssh_execute"]
        result = json.loads(await tool.run({
            "hostname": "10.0.0.1",
            "command": "sudo systemctl status datadog-agent",
        }))
        assert result["exit_code"] == 0
        assert "running" in result["stdout"]
        client.post.assert_called_once_with(
            "/api/ssh/execute",
            {"hostname": "10.0.0.1", "command": "sudo systemctl status datadog-agent", "username": "ec2-user"},
        )

    async def test_custom_username(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.post.return_value = {"stdout": "", "stderr": "", "exit_code": 0, "hostname": "10.0.0.1"}
        tool = mcp._tool_manager._tools["ssh_execute"]
        await tool.run({
            "hostname": "10.0.0.1",
            "command": "whoami",
            "username": "ubuntu",
        })
        posted_body = client.post.call_args[0][1]
        assert posted_body["username"] == "ubuntu"

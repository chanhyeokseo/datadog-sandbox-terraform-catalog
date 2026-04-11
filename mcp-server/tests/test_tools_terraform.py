import json
import pytest
from mcp.server.fastmcp import FastMCP

from tools.terraform import register


@pytest.fixture
def mcp_with_tools(mock_client):
    mcp = FastMCP("test")
    register(mcp, mock_client)
    return mcp, mock_client


class TestTerraformPlan:

    async def test_returns_plan_output(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_get.return_value = {
            "success": True, "exit_code": 0,
            "output": "Plan: 1 to add, 0 to change, 0 to destroy.",
        }
        tool = mcp._tool_manager._tools["terraform_plan"]
        result = json.loads(await tool.run({"resource_id": "ec2_basic"}))
        assert result["success"] is True
        assert "1 to add" in result["output"]

    async def test_failed_plan(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_get.return_value = {
            "success": False, "exit_code": 1, "output": "Error: Missing required argument",
        }
        tool = mcp._tool_manager._tools["terraform_plan"]
        result = json.loads(await tool.run({"resource_id": "ec2_basic"}))
        assert result["success"] is False
        assert result["exit_code"] == 1


class TestTerraformApply:

    async def test_passes_auto_approve(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_get.return_value = {"success": True, "exit_code": 0, "output": "Apply complete!"}
        tool = mcp._tool_manager._tools["terraform_apply"]
        await tool.run({"resource_id": "ec2_basic"})
        client.stream_get.assert_called_once_with(
            "/api/terraform/apply/stream/ec2_basic", auto_approve="true"
        )


class TestTerraformDestroy:

    async def test_passes_auto_approve(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_get.return_value = {"success": True, "exit_code": 0, "output": "Destroy complete!"}
        tool = mcp._tool_manager._tools["terraform_destroy"]
        await tool.run({"resource_id": "ec2_basic"})
        client.stream_get.assert_called_once_with(
            "/api/terraform/destroy/stream/ec2_basic", auto_approve="true"
        )


class TestTerraformOutput:

    async def test_parses_json_output(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {
            "success": True,
            "output": json.dumps({
                "instance_id": {"value": "i-abc123"},
                "public_ip": {"value": "54.180.1.100"},
            }),
        }
        tool = mcp._tool_manager._tools["terraform_output"]
        result = json.loads(await tool.run({"resource_id": "ec2_basic"}))
        assert result["success"] is True
        assert result["outputs"]["instance_id"] == "i-abc123"
        assert result["outputs"]["public_ip"] == "54.180.1.100"

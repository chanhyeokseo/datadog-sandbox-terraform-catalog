import json
import pytest
from mcp.server.fastmcp import FastMCP

from tools.resource import register


@pytest.fixture
def mcp_with_tools(mock_client):
    mcp = FastMCP("test")
    register(mcp, mock_client)
    return mcp, mock_client


class TestListResources:

    async def test_returns_resource_list(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = [
            {"id": "ec2_basic", "name": "ec2_basic", "type": "ec2", "status": "disabled", "description": "Basic EC2"},
            {"id": "eks_cluster", "name": "eks_cluster", "type": "eks", "status": "enabled", "description": "EKS"},
        ]
        tool = mcp._tool_manager._tools["list_resources"]
        result = json.loads(await tool.run({}))
        assert len(result) == 2
        assert result[0]["id"] == "ec2_basic"
        client.get.assert_called_once_with("/api/terraform/resources")


class TestGetResourceDetails:

    async def test_returns_variables_and_description(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.side_effect = [
            [{"name": "ec2_instance_type", "value": "t3.micro", "sensitive": False}],
            {"content": "EC2 basic instance"},
        ]
        tool = mcp._tool_manager._tools["get_resource_details"]
        result = json.loads(await tool.run({"resource_id": "ec2_basic"}))
        assert result["resource_id"] == "ec2_basic"
        assert result["description"] == "EC2 basic instance"
        assert len(result["variables"]) == 1


class TestSetVariable:

    async def test_root_level_variable(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.put.return_value = {"success": True, "message": "Variable updated"}
        tool = mcp._tool_manager._tools["set_variable"]
        result = json.loads(await tool.run({"variable_name": "region", "value": "us-east-1"}))
        assert result["success"] is True
        client.put.assert_called_once_with(
            "/api/terraform/variables/region", {"value": "us-east-1"}
        )

    async def test_resource_level_variable(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.put.return_value = {"success": True, "message": "Variable updated"}
        tool = mcp._tool_manager._tools["set_variable"]
        result = json.loads(await tool.run({
            "variable_name": "ec2_instance_type",
            "value": "t3.micro",
            "resource_id": "ec2_basic",
        }))
        assert result["success"] is True
        client.put.assert_called_once_with(
            "/api/terraform/resources/ec2_basic/variables/ec2_instance_type",
            {"value": "t3.micro"},
        )

import json
import pytest
from mcp.server.fastmcp import FastMCP

from tools.ecs import register


@pytest.fixture
def mcp_with_tools(mock_client):
    mcp = FastMCP("test")
    register(mcp, mock_client)
    return mcp, mock_client


class TestListECSPresets:

    async def test_returns_preset_summary(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {
            "presets": [
                {"name": "datadog-linux", "description": "DD Agent", "type": "aws-ecs", "built_in": True},
            ]
        }
        tool = mcp._tool_manager._tools["list_ecs_presets"]
        result = json.loads(await tool.run({}))
        assert len(result) == 1
        assert result[0]["name"] == "datadog-linux"


class TestDeployECSPreset:

    async def test_calls_deploy_stream(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_post.return_value = {"success": True, "exit_code": 0, "output": "deployed"}
        tool = mcp._tool_manager._tools["deploy_ecs_preset"]
        result = json.loads(await tool.run({"preset_name": "datadog-linux"}))
        assert result["success"] is True


class TestUndeployECSPreset:

    async def test_calls_undeploy_stream(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_post.return_value = {"success": True, "exit_code": 0, "output": "undeployed"}
        tool = mcp._tool_manager._tools["undeploy_ecs_preset"]
        result = json.loads(await tool.run({"preset_name": "datadog-linux"}))
        assert result["success"] is True


class TestGetECSClusterStatus:

    async def test_returns_cluster_info(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"configured": True, "cluster_name": "my-cluster", "region": "ap-northeast-2"}
        tool = mcp._tool_manager._tools["get_ecs_cluster_status"]
        result = json.loads(await tool.run({}))
        assert result["configured"] is True
        assert result["cluster_name"] == "my-cluster"


class TestGetECSActiveWorkloads:

    async def test_returns_workloads(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {
            "has_active": True,
            "services": [{"name": "dd-agent", "status": "ACTIVE", "running": 1, "desired": 1}],
            "running_tasks": 1,
            "deployed_presets": ["datadog-linux"],
        }
        tool = mcp._tool_manager._tools["get_ecs_active_workloads"]
        result = json.loads(await tool.run({}))
        assert result["has_active"] is True
        assert result["running_tasks"] == 1


class TestGetECSContainerInstances:

    async def test_returns_instances(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {
            "cluster_name": "my-cluster",
            "instances": [{"instance_id": "i-abc", "public_ip": "1.2.3.4", "state": "running"}],
        }
        tool = mcp._tool_manager._tools["get_ecs_container_instances"]
        result = json.loads(await tool.run({}))
        assert len(result["instances"]) == 1


class TestRunECSCommand:

    async def test_returns_command_output(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_post.return_value = {
            "success": True, "exit_code": 0,
            "output": json.dumps({"serviceArns": ["arn:aws:ecs:ap-northeast-2:123:service/my-svc"]}),
        }
        tool = mcp._tool_manager._tools["run_ecs_command"]
        result = await tool.run({"command": "aws ecs list-services"})
        assert "my-svc" in result

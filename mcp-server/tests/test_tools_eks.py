import json
import pytest
from mcp.server.fastmcp import FastMCP

from tools.eks import register


@pytest.fixture
def mcp_with_tools(mock_client):
    mcp = FastMCP("test")
    register(mcp, mock_client)
    return mcp, mock_client


class TestListEKSPresets:

    async def test_returns_preset_summary(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {
            "presets": [
                {"name": "agent-helm", "description": "DD Agent", "type": "helm", "built_in": True, "extra": "ignored"},
                {"name": "nginx", "description": "Nginx", "type": "kubectl", "built_in": True},
            ]
        }
        tool = mcp._tool_manager._tools["list_eks_presets"]
        result = json.loads(await tool.run({}))
        assert len(result) == 2
        assert result[0]["name"] == "agent-helm"
        assert "extra" not in result[0]


class TestDeployEKSPreset:

    async def test_calls_deploy_stream(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_post.return_value = {"success": True, "exit_code": 0, "output": "deployed"}
        tool = mcp._tool_manager._tools["deploy_eks_preset"]
        result = json.loads(await tool.run({"preset_name": "agent-helm"}))
        assert result["success"] is True
        client.stream_post.assert_called_once_with("/api/terraform/eks/manage/presets/agent-helm/deploy")


class TestUndeployEKSPreset:

    async def test_calls_undeploy_stream(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_post.return_value = {"success": True, "exit_code": 0, "output": "undeployed"}
        tool = mcp._tool_manager._tools["undeploy_eks_preset"]
        result = json.loads(await tool.run({"preset_name": "agent-helm"}))
        assert result["success"] is True


class TestRunKubectl:

    async def test_returns_command_output(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_post.return_value = {
            "success": True, "exit_code": 0,
            "output": "NAME    READY   STATUS\nnginx   1/1     Running",
        }
        tool = mcp._tool_manager._tools["run_kubectl"]
        result = await tool.run({"command": "kubectl get pods"})
        assert "nginx" in result
        client.stream_post.assert_called_once_with(
            "/api/terraform/eks/manage/kubectl",
            {"command": "kubectl get pods"},
        )


class TestGetEKSDeployments:

    async def test_returns_deployments(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"deployments": {"agent-helm": {"deployed_at": "2026-04-11T00:00:00Z"}}}
        tool = mcp._tool_manager._tools["get_eks_deployments"]
        result = json.loads(await tool.run({}))
        assert "agent-helm" in result["deployments"]

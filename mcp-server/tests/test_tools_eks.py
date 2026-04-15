import json
import pytest
from mcp.server.fastmcp import FastMCP

from tools.eks import register


@pytest.fixture
def mcp_with_tools(mock_client):
    mcp = FastMCP("test")
    register(mcp, mock_client)
    return mcp, mock_client


def _tool(mcp, name):
    return mcp._tool_manager._tools[name]


class TestGetEKSPresetInfo:

    async def test_returns_preset_summary(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {
            "presets": [
                {"name": "agent-helm", "description": "DD Agent", "type": "helm", "built_in": True, "extra": "ignored"},
                {"name": "nginx", "description": "Nginx", "type": "kubectl", "built_in": True},
            ]
        }
        result = json.loads(await _tool(mcp, "get_eks_preset_info").run({}))
        assert len(result) == 2
        assert result[0]["name"] == "agent-helm"
        assert "extra" not in result[0]

    async def test_shared_preset_list(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {
            "presets": [
                {"name": "shared-app", "description": "Shared", "type": "kubectl", "built_in": False},
            ]
        }
        result = json.loads(await _tool(mcp, "get_eks_preset_info").run(
            {"owner_prefix": "other-user"}
        ))
        assert len(result) == 1
        assert result[0]["name"] == "shared-app"
        client.get.assert_called_once_with(
            "/api/terraform/eks/manage/shared-presets",
            owner_prefix="other-user",
        )

    async def test_shared_preset_detail(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"name": "shared-app", "files": ["deploy.yaml"]}
        await _tool(mcp, "get_eks_preset_info").run(
            {"preset_name": "shared-app", "owner_prefix": "other-user"}
        )
        client.get.assert_called_once_with(
            "/api/terraform/eks/manage/shared-presets/shared-app",
            owner_prefix="other-user",
        )

    async def test_shared_preset_file(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"filename": "deploy.yaml", "content": "apiVersion: v1"}
        await _tool(mcp, "get_eks_preset_info").run(
            {"preset_name": "shared-app", "filename": "deploy.yaml", "owner_prefix": "other-user"}
        )
        client.get.assert_called_once_with(
            "/api/terraform/eks/manage/shared-presets/shared-app/files/deploy.yaml",
            owner_prefix="other-user",
        )


class TestManageEKSDeployment:

    async def test_deploy_calls_stream(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_post.return_value = {"success": True, "exit_code": 0, "output": "deployed"}
        result = json.loads(await _tool(mcp, "manage_eks_deployment").run(
            {"action": "deploy", "preset_name": "agent-helm"}
        ))
        assert result["success"] is True
        client.stream_post.assert_called_once_with(
            "/api/terraform/eks/manage/presets/agent-helm/deploy",
            params=None,
        )

    async def test_undeploy_calls_stream(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_post.return_value = {"success": True, "exit_code": 0, "output": "undeployed"}
        result = json.loads(await _tool(mcp, "manage_eks_deployment").run(
            {"action": "undeploy", "preset_name": "agent-helm"}
        ))
        assert result["success"] is True

    async def test_list_returns_deployments(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"deployments": {"agent-helm": {"deployed_at": "2026-04-11T00:00:00Z"}}}
        result = json.loads(await _tool(mcp, "manage_eks_deployment").run({"action": "list"}))
        assert "agent-helm" in result["deployments"]

    async def test_deploy_on_shared_cluster(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_post.return_value = {"success": True, "exit_code": 0, "output": "deployed"}
        await _tool(mcp, "manage_eks_deployment").run({
            "action": "deploy",
            "preset_name": "nginx",
            "cluster_name": "shared-eks-cluster",
            "owner_prefix": "other-user",
        })
        client.stream_post.assert_called_once_with(
            "/api/terraform/eks/manage/presets/nginx/deploy",
            params={"cluster_name": "shared-eks-cluster", "owner_prefix": "other-user"},
        )

    async def test_undeploy_on_shared_cluster(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_post.return_value = {"success": True, "exit_code": 0, "output": "undeployed"}
        await _tool(mcp, "manage_eks_deployment").run({
            "action": "undeploy",
            "preset_name": "nginx",
            "cluster_name": "shared-eks-cluster",
            "owner_prefix": "other-user",
        })
        client.stream_post.assert_called_once_with(
            "/api/terraform/eks/manage/presets/nginx/undeploy",
            params={"cluster_name": "shared-eks-cluster", "owner_prefix": "other-user"},
        )

    async def test_list_shared_deployments(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"deployments": {"nginx": {"deployed_at": "2026-04-12T00:00:00Z"}}}
        result = json.loads(await _tool(mcp, "manage_eks_deployment").run(
            {"action": "list", "owner_prefix": "other-user"}
        ))
        assert "nginx" in result["deployments"]
        client.get.assert_called_once_with(
            "/api/terraform/eks/manage/shared-deployments",
            owner_prefix="other-user",
        )

    async def test_invalid_action(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        result = json.loads(await _tool(mcp, "manage_eks_deployment").run({"action": "bad"}))
        assert "error" in result


class TestRunKubectl:

    async def test_returns_command_output(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_post.return_value = {
            "success": True, "exit_code": 0,
            "output": "NAME    READY   STATUS\nnginx   1/1     Running",
        }
        result = await _tool(mcp, "run_kubectl").run({"command": "kubectl get pods"})
        assert "nginx" in result
        client.stream_post.assert_called_once_with(
            "/api/terraform/eks/manage/kubectl",
            {"command": "kubectl get pods"},
        )

    async def test_run_on_shared_cluster(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_post.return_value = {
            "success": True, "exit_code": 0,
            "output": "NAME    READY   STATUS\nnginx   1/1     Running",
        }
        await _tool(mcp, "run_kubectl").run({
            "command": "kubectl get pods",
            "cluster_name": "shared-eks-cluster",
        })
        client.stream_post.assert_called_once_with(
            "/api/terraform/eks/manage/kubectl",
            {"command": "kubectl get pods", "cluster_name": "shared-eks-cluster"},
        )


class TestListSharedClusters:

    async def test_returns_shared_clusters(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {
            "clusters": [
                {"cluster_name": "other-eks-cluster", "cluster_arn": "arn:aws:eks:...", "owner_prefix": "other-user", "shared_at": "2026-04-10T00:00:00Z"},
            ]
        }
        result = json.loads(await _tool(mcp, "list_shared_clusters").run({}))
        assert len(result["clusters"]) == 1
        assert result["clusters"][0]["owner_prefix"] == "other-user"
        client.get.assert_called_once_with("/api/cluster-share/shared")

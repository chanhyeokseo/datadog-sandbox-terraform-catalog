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


class TestUpdateEKSPreset:

    async def test_file_mode(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.put.return_value = {"success": True}
        result = json.loads(await _tool(mcp, "update_eks_preset").run({
            "preset_name": "my-preset",
            "filename": "deploy.yaml",
            "content": "apiVersion: v1",
        }))
        assert result["success"] is True
        client.put.assert_called_once_with(
            "/api/terraform/eks/manage/presets/my-preset/files/deploy.yaml",
            {"content": "apiVersion: v1"},
        )

    async def test_delete_file_mode(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.delete.return_value = {"success": True}
        result = json.loads(await _tool(mcp, "update_eks_preset").run({
            "preset_name": "my-preset",
            "delete_file": "old.yaml",
        }))
        assert result["success"] is True
        client.delete.assert_called_once_with(
            "/api/terraform/eks/manage/presets/my-preset/files/old.yaml",
        )

    async def test_rename_file_mode(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.post.return_value = {"success": True, "new_filename": "new.yaml"}
        result = json.loads(await _tool(mcp, "update_eks_preset").run({
            "preset_name": "my-preset",
            "rename_file": "old.yaml",
            "new_filename": "new.yaml",
        }))
        assert result["success"] is True
        client.post.assert_called_once_with(
            "/api/terraform/eks/manage/presets/my-preset/files/old.yaml/rename",
            {"new_filename": "new.yaml"},
        )

    async def test_rename_file_missing_new_filename(self, mcp_with_tools):
        mcp, _ = mcp_with_tools
        result = json.loads(await _tool(mcp, "update_eks_preset").run({
            "preset_name": "my-preset",
            "rename_file": "old.yaml",
        }))
        assert "error" in result

    async def test_manifest_mode(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.put.return_value = {"success": True}
        result = json.loads(await _tool(mcp, "update_eks_preset").run({
            "preset_name": "my-preset",
            "description": "Updated desc",
        }))
        assert result["success"] is True
        client.put.assert_called_once_with(
            "/api/terraform/eks/manage/presets/my-preset",
            {"description": "Updated desc"},
        )


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


class TestManageClusterShare:

    async def test_list_shareable_clusters(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {
            "clusters": [{"name": "my-eks", "arn": "arn:aws:eks:ap-northeast-2:123:cluster/my-eks", "status": "ACTIVE", "owner_prefix": "user-a"}],
            "my_prefix": "user-b",
        }
        result = json.loads(await _tool(mcp, "manage_cluster_share").run({"action": "list_shareable_clusters"}))
        assert result["my_prefix"] == "user-b"
        client.get.assert_called_once_with("/api/cluster-share/clusters")

    async def test_request_share(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.post.return_value = {"id": "req-1", "status": "pending"}
        result = json.loads(await _tool(mcp, "manage_cluster_share").run({
            "action": "request",
            "cluster_name": "other-eks",
            "cluster_arn": "arn:aws:eks:ap-northeast-2:123:cluster/other-eks",
            "owner_prefix": "user-a",
        }))
        assert result["status"] == "pending"
        client.post.assert_called_once_with("/api/cluster-share/requests", {
            "cluster_name": "other-eks",
            "cluster_arn": "arn:aws:eks:ap-northeast-2:123:cluster/other-eks",
            "owner_prefix": "user-a",
        })

    async def test_request_missing_fields(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        result = json.loads(await _tool(mcp, "manage_cluster_share").run({
            "action": "request", "cluster_name": "x",
        }))
        assert "error" in result

    async def test_list_incoming(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"requests": [{"id": "r1", "status": "pending"}]}
        result = json.loads(await _tool(mcp, "manage_cluster_share").run({"action": "list_incoming"}))
        assert len(result["requests"]) == 1
        client.get.assert_called_once_with("/api/cluster-share/requests/incoming")

    async def test_list_outgoing(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"requests": [{"id": "r2", "status": "approved"}]}
        result = json.loads(await _tool(mcp, "manage_cluster_share").run({"action": "list_outgoing"}))
        assert result["requests"][0]["id"] == "r2"
        client.get.assert_called_once_with("/api/cluster-share/requests/outgoing")

    async def test_approve(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.post.return_value = {"id": "r1", "status": "approved"}
        result = json.loads(await _tool(mcp, "manage_cluster_share").run({
            "action": "approve", "request_id": "r1",
        }))
        assert result["status"] == "approved"
        client.post.assert_called_once_with("/api/cluster-share/requests/r1/approve")

    async def test_deny(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.post.return_value = {"id": "r1", "status": "denied"}
        result = json.loads(await _tool(mcp, "manage_cluster_share").run({
            "action": "deny", "request_id": "r1",
        }))
        assert result["status"] == "denied"
        client.post.assert_called_once_with("/api/cluster-share/requests/r1/deny")

    async def test_delete(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.delete.return_value = {"success": True}
        result = json.loads(await _tool(mcp, "manage_cluster_share").run({
            "action": "delete", "request_id": "r1",
        }))
        assert result["success"] is True
        client.delete.assert_called_once_with("/api/cluster-share/requests/r1")

    async def test_approve_missing_request_id(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        result = json.loads(await _tool(mcp, "manage_cluster_share").run({"action": "approve"}))
        assert "error" in result

    async def test_invalid_action(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        result = json.loads(await _tool(mcp, "manage_cluster_share").run({"action": "bad"}))
        assert "error" in result


    async def test_list_approved(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {
            "clusters": [
                {"cluster_name": "other-eks-cluster", "cluster_arn": "arn:aws:eks:...", "owner_prefix": "other-user", "shared_at": "2026-04-10T00:00:00Z"},
            ]
        }
        result = json.loads(await _tool(mcp, "manage_cluster_share").run({"action": "list_approved"}))
        assert len(result["clusters"]) == 1
        assert result["clusters"][0]["owner_prefix"] == "other-user"
        client.get.assert_called_once_with("/api/cluster-share/shared")


class TestConfigureEKSCluster:

    _CURRENT_CONFIG = {
        "enable_node_group": True,
        "node_instance_types": ["t3.medium"],
        "node_desired_size": 2,
        "node_min_size": 1,
        "node_max_size": 4,
        "node_disk_size": 20,
        "node_capacity_type": "ON_DEMAND",
        "enable_windows_node_group": False,
        "windows_node_instance_types": ["t3.medium"],
        "windows_node_ami_type": "WINDOWS_FULL_2022_x86_64",
        "windows_node_desired_size": 2,
        "windows_node_min_size": 1,
        "windows_node_max_size": 4,
        "windows_node_disk_size": 50,
        "windows_node_capacity_type": "ON_DEMAND",
        "enable_fargate": False,
        "fargate_namespaces": ["default", "kube-system"],
        "endpoint_public_access": True,
        "endpoint_private_access": True,
    }

    async def test_get_current_config(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = dict(self._CURRENT_CONFIG)
        result = json.loads(await _tool(mcp, "configure_eks_cluster").run({}))
        assert result["enable_fargate"] is False
        assert result["node_desired_size"] == 2
        client.get.assert_called_once_with("/api/terraform/eks/config")
        client.post.assert_not_called()

    async def test_partial_update_merges_and_posts(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = dict(self._CURRENT_CONFIG)
        client.post.return_value = {"success": True, "message": "EKS configuration updated successfully"}
        result = json.loads(await _tool(mcp, "configure_eks_cluster").run({
            "enable_fargate": True,
            "fargate_namespaces": ["default"],
        }))
        assert result["success"] is True
        assert "enable_fargate" in result["updated_fields"]
        assert "fargate_namespaces" in result["updated_fields"]
        posted_config = client.post.call_args[0][1]
        assert posted_config["enable_fargate"] is True
        assert posted_config["fargate_namespaces"] == ["default"]
        assert posted_config["node_desired_size"] == 2

    async def test_returns_error_when_config_unavailable(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"error": "EKS resource not found"}
        result = json.loads(await _tool(mcp, "configure_eks_cluster").run({
            "enable_fargate": True,
        }))
        assert "error" in result
        client.post.assert_not_called()

    async def test_single_field_update(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = dict(self._CURRENT_CONFIG)
        client.post.return_value = {"success": True, "message": "EKS configuration updated successfully"}
        result = json.loads(await _tool(mcp, "configure_eks_cluster").run({
            "node_capacity_type": "SPOT",
        }))
        assert result["updated_fields"] == ["node_capacity_type"]
        posted_config = client.post.call_args[0][1]
        assert posted_config["node_capacity_type"] == "SPOT"

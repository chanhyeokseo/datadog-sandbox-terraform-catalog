import json
import pytest
from mcp.server.fastmcp import FastMCP

from tools.ecs import register


@pytest.fixture
def mcp_with_tools(mock_client):
    mcp = FastMCP("test")
    register(mcp, mock_client)
    return mcp, mock_client


class TestGetECSStatus:

    async def test_returns_cluster_info(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"configured": True, "cluster_name": "my-cluster", "region": "ap-northeast-2"}
        tool = mcp._tool_manager._tools["get_ecs_status"]
        result = json.loads(await tool.run({"info_type": "cluster"}))
        assert result["configured"] is True
        assert result["cluster_name"] == "my-cluster"

    async def test_rejects_invalid_info_type(self, mcp_with_tools):
        mcp, _ = mcp_with_tools
        tool = mcp._tool_manager._tools["get_ecs_status"]
        result = json.loads(await tool.run({"info_type": "invalid"}))
        assert "error" in result


class TestManageECSDeployment:

    async def test_list_returns_deployments(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"deployments": {"datadog-linux": {"deployed_at": "2025-01-01T00:00:00Z"}}}
        tool = mcp._tool_manager._tools["manage_ecs_deployment"]
        result = json.loads(await tool.run({"action": "list"}))
        assert "deployments" in result
        client.get.assert_called_once_with("/api/terraform/ecs/manage/deployments")

    async def test_deploy_calls_stream(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_post.return_value = {"success": True, "exit_code": 0, "output": "deployed"}
        tool = mcp._tool_manager._tools["manage_ecs_deployment"]
        result = json.loads(await tool.run({"action": "deploy", "preset_name": "datadog-linux"}))
        assert result["success"] is True
        client.stream_post.assert_called_once_with("/api/terraform/ecs/manage/presets/datadog-linux/deploy")

    async def test_update_calls_stream(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_post.return_value = {"success": True, "exit_code": 0, "output": "updated"}
        tool = mcp._tool_manager._tools["manage_ecs_deployment"]
        result = json.loads(await tool.run({"action": "update", "preset_name": "my-preset"}))
        assert result["success"] is True
        client.stream_post.assert_called_once_with("/api/terraform/ecs/manage/presets/my-preset/update")

    async def test_undeploy_calls_stream(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.stream_post.return_value = {"success": True, "exit_code": 0, "output": "undeployed"}
        tool = mcp._tool_manager._tools["manage_ecs_deployment"]
        result = json.loads(await tool.run({"action": "undeploy", "preset_name": "datadog-linux"}))
        assert result["success"] is True

    async def test_rejects_missing_preset_name(self, mcp_with_tools):
        mcp, _ = mcp_with_tools
        tool = mcp._tool_manager._tools["manage_ecs_deployment"]
        result = json.loads(await tool.run({"action": "deploy"}))
        assert "error" in result

    async def test_rejects_invalid_action(self, mcp_with_tools):
        mcp, _ = mcp_with_tools
        tool = mcp._tool_manager._tools["manage_ecs_deployment"]
        result = json.loads(await tool.run({"action": "invalid"}))
        assert "error" in result


class TestGetECSPresetInfo:

    async def test_list_all_presets(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {
            "presets": [
                {"name": "nginx", "description": "Nginx", "type": "aws-ecs", "built_in": True, "files": ["task-definition.json"]},
            ]
        }
        tool = mcp._tool_manager._tools["get_ecs_preset_info"]
        result = json.loads(await tool.run({}))
        assert len(result) == 1
        assert result[0]["files"] == ["task-definition.json"]

    async def test_get_preset_details(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"name": "nginx", "description": "Nginx", "files": ["task-definition.json"]}
        tool = mcp._tool_manager._tools["get_ecs_preset_info"]
        result = json.loads(await tool.run({"preset_name": "nginx"}))
        assert result["name"] == "nginx"
        client.get.assert_called_once_with("/api/terraform/ecs/manage/presets/nginx")

    async def test_get_preset_file_content(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"filename": "task-definition.json", "content": '{"family": "nginx"}'}
        tool = mcp._tool_manager._tools["get_ecs_preset_info"]
        result = json.loads(await tool.run({"preset_name": "nginx", "filename": "task-definition.json"}))
        assert result["filename"] == "task-definition.json"
        client.get.assert_called_once_with("/api/terraform/ecs/manage/presets/nginx/files/task-definition.json")


class TestCreateECSPreset:

    async def test_creates_preset(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.post.return_value = {"success": True, "name": "my-preset"}
        tool = mcp._tool_manager._tools["create_ecs_preset"]
        result = json.loads(await tool.run({
            "preset_name": "my-preset",
            "description": "Test preset",
            "files": {"task-definition.json": '{"family": "test"}'},
        }))
        assert result["success"] is True
        client.post.assert_called_once_with("/api/terraform/ecs/manage/presets", {
            "name": "my-preset",
            "description": "Test preset",
            "type": "aws-ecs",
            "files": {"task-definition.json": '{"family": "test"}'},
        })


class TestCloneECSPreset:

    async def test_clones_preset(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.post.return_value = {"success": True, "name": "my-copy"}
        tool = mcp._tool_manager._tools["clone_ecs_preset"]
        result = json.loads(await tool.run({"preset_name": "datadog-linux", "target_name": "my-copy"}))
        assert result["success"] is True
        client.post.assert_called_once_with(
            "/api/terraform/ecs/manage/presets/datadog-linux/clone",
            {"target_name": "my-copy"},
        )


class TestUpdateECSPreset:

    async def test_update_file_mode(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.put.return_value = {"success": True}
        tool = mcp._tool_manager._tools["update_ecs_preset"]
        result = json.loads(await tool.run({
            "preset_name": "my-preset",
            "filename": "task-definition.json",
            "content": '{"family": "updated"}',
        }))
        assert result["success"] is True
        client.put.assert_called_once_with(
            "/api/terraform/ecs/manage/presets/my-preset/files/task-definition.json",
            {"content": '{"family": "updated"}'},
        )

    async def test_update_manifest_mode(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.put.return_value = {"success": True}
        tool = mcp._tool_manager._tools["update_ecs_preset"]
        result = json.loads(await tool.run({
            "preset_name": "my-preset",
            "description": "Updated desc",
        }))
        assert result["success"] is True
        client.put.assert_called_once_with(
            "/api/terraform/ecs/manage/presets/my-preset",
            {"description": "Updated desc"},
        )


class TestUpdateECSPresetDeleteFile:

    async def test_delete_file_mode(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.delete.return_value = {"success": True}
        tool = mcp._tool_manager._tools["update_ecs_preset"]
        result = json.loads(await tool.run({
            "preset_name": "my-preset",
            "delete_file": "old-file.json",
        }))
        assert result["success"] is True
        client.delete.assert_called_once_with(
            "/api/terraform/ecs/manage/presets/my-preset/files/old-file.json",
        )


class TestUpdateECSPresetRenameFile:

    async def test_rename_file_mode(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.post.return_value = {"success": True, "new_filename": "new-file.json"}
        tool = mcp._tool_manager._tools["update_ecs_preset"]
        result = json.loads(await tool.run({
            "preset_name": "my-preset",
            "rename_file": "old-file.json",
            "new_filename": "new-file.json",
        }))
        assert result["success"] is True
        client.post.assert_called_once_with(
            "/api/terraform/ecs/manage/presets/my-preset/files/old-file.json/rename",
            {"new_filename": "new-file.json"},
        )

    async def test_rename_file_missing_new_filename(self, mcp_with_tools):
        mcp, _ = mcp_with_tools
        tool = mcp._tool_manager._tools["update_ecs_preset"]
        result = json.loads(await tool.run({
            "preset_name": "my-preset",
            "rename_file": "old-file.json",
        }))
        assert "error" in result


class TestDeleteECSPreset:

    async def test_deletes_preset(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.delete.return_value = {"success": True}
        tool = mcp._tool_manager._tools["delete_ecs_preset"]
        result = json.loads(await tool.run({"preset_name": "my-preset"}))
        assert result["success"] is True
        client.delete.assert_called_once_with("/api/terraform/ecs/manage/presets/my-preset")


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


class TestQueryCloudwatchLogs:

    async def test_queries_logs(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.post.return_value = {
            "log_group": "/ecs/test",
            "event_count": 1,
            "events": [{"timestamp": 1234567890, "message": "test log", "logStreamName": "stream-1"}],
        }
        tool = mcp._tool_manager._tools["query_cloudwatch_logs"]
        result = json.loads(await tool.run({"log_group": "/ecs/test"}))
        assert result["event_count"] == 1
        assert result["events"][0]["message"] == "test log"

    async def test_passes_filter_pattern(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.post.return_value = {"log_group": "/ecs/test", "event_count": 0, "events": []}
        tool = mcp._tool_manager._tools["query_cloudwatch_logs"]
        await tool.run({
            "log_group": "/ecs/test",
            "filter_pattern": '{ $.status = "error" }',
            "start_time": "2025-01-01T00:00:00Z",
            "limit": 50,
        })
        client.post.assert_called_once()
        call_body = client.post.call_args[0][1]
        assert call_body["filter_pattern"] == '{ $.status = "error" }'
        assert call_body["start_time"] == "2025-01-01T00:00:00Z"
        assert call_body["limit"] == 50

    async def test_caps_limit_at_1000(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.post.return_value = {"log_group": "/ecs/test", "event_count": 0, "events": []}
        tool = mcp._tool_manager._tools["query_cloudwatch_logs"]
        await tool.run({"log_group": "/ecs/test", "limit": 9999})
        call_body = client.post.call_args[0][1]
        assert call_body["limit"] == 1000

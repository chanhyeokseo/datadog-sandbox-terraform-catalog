import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.services.ecs_preset_manager import ECSPresetManager


@pytest.fixture
def ecs_env(tmp_path):
    ecs_dir = tmp_path / "ecs"
    ecs_dir.mkdir()

    linux_dir = ecs_dir / "datadog-linux"
    linux_dir.mkdir()
    (linux_dir / "manifest.json").write_text(json.dumps({
        "name": "datadog-linux",
        "description": "Datadog Agent for ECS EC2 (Linux)",
        "type": "aws-ecs",
        "built_in": True,
        "files": ["task-definition.json"],
    }))
    (linux_dir / "task-definition.json").write_text(json.dumps({
        "family": "datadog-agent",
        "containerDefinitions": [{"name": "datadog-agent", "image": "datadog/agent:latest"}],
    }))

    nginx_dir = ecs_dir / "nginx"
    nginx_dir.mkdir()
    (nginx_dir / "manifest.json").write_text(json.dumps({
        "name": "nginx",
        "description": "Plain nginx",
        "type": "aws-ecs",
        "built_in": True,
        "files": ["task-definition.json"],
    }))
    (nginx_dir / "task-definition.json").write_text(json.dumps({
        "family": "nginx",
        "containerDefinitions": [{"name": "nginx", "image": "nginx:latest"}],
    }))

    return tmp_path


@pytest.fixture
def manager(ecs_env):
    mgr = ECSPresetManager(str(ecs_env))
    mgr._get_s3_manager = lambda: None
    return mgr


class TestListPresets:

    def test_returns_built_in(self, manager):
        presets = manager.list_presets()
        names = {p["name"] for p in presets}
        assert "datadog-linux" in names
        assert "nginx" in names
        for p in presets:
            assert p["built_in"] is True


class TestGetPreset:

    def test_returns_details(self, manager):
        preset = manager.get_preset("datadog-linux")
        assert preset is not None
        assert preset["name"] == "datadog-linux"
        assert "task-definition.json" in preset["files"]

    def test_returns_none_for_missing(self, manager):
        assert manager.get_preset("nonexistent") is None


class TestGetPresetFile:

    def test_returns_content(self, manager):
        content = manager.get_preset_file("datadog-linux", "task-definition.json")
        assert content is not None
        td = json.loads(content)
        assert td["family"] == "datadog-agent"

    def test_returns_none_for_missing_file(self, manager):
        assert manager.get_preset_file("datadog-linux", "nonexistent.json") is None


class TestCreatePreset:

    def test_creates_custom_preset(self, manager):
        td = json.dumps({
            "family": "my-app",
            "containerDefinitions": [{"name": "app", "image": "my-app:latest"}],
            "requiresCompatibilities": ["FARGATE"],
            "networkMode": "awsvpc",
            "cpu": "256",
            "memory": "512",
        })
        result = manager.create_preset(
            name="my-fargate-app",
            description="Custom Fargate app",
            preset_type="aws-ecs",
            files={"task-definition.json": td},
        )
        assert result is True

        preset = manager.get_preset("my-fargate-app")
        assert preset is not None
        assert preset["name"] == "my-fargate-app"
        assert preset["built_in"] is False

        content = manager.get_preset_file("my-fargate-app", "task-definition.json")
        parsed = json.loads(content)
        assert "FARGATE" in parsed["requiresCompatibilities"]

    def test_fails_for_existing(self, manager):
        assert manager.create_preset(name="datadog-linux") is False


class TestClonePreset:

    def test_clones_built_in(self, manager):
        result = manager.clone_preset("datadog-linux", "my-dd-copy")
        assert result is True

        clone = manager.get_preset("my-dd-copy")
        assert clone is not None
        assert clone["name"] == "my-dd-copy"
        assert clone["built_in"] is False

        content = manager.get_preset_file("my-dd-copy", "task-definition.json")
        assert content is not None
        td = json.loads(content)
        assert td["family"] == "datadog-agent"

    def test_fails_for_existing_target(self, manager):
        assert manager.clone_preset("datadog-linux", "nginx") is False


class TestDeletePreset:

    def test_blocks_built_in(self, manager):
        assert manager.delete_preset("datadog-linux") is False

    def test_deletes_custom(self, manager):
        manager.create_preset(name="temp", description="temp")
        assert manager.get_preset("temp") is not None
        assert manager.delete_preset("temp") is True
        assert manager.get_preset("temp") is None


class TestSavePresetFile:

    def test_updates_file(self, manager):
        manager.create_preset(
            name="editable",
            description="test",
            files={"task-definition.json": '{"family": "old"}'},
        )
        result = manager.save_preset_file("editable", "task-definition.json", '{"family": "new"}')
        assert result is True

        content = manager.get_preset_file("editable", "task-definition.json")
        assert json.loads(content)["family"] == "new"


class TestDeploymentTracking:

    def test_mark_deployed_and_undeployed(self, manager):
        manager.mark_deployed("datadog-linux")
        deployments = manager.get_deployments()
        assert "datadog-linux" in deployments
        assert "deployed_at" in deployments["datadog-linux"]

        manager.mark_undeployed("datadog-linux")
        deployments = manager.get_deployments()
        assert "datadog-linux" not in deployments


class TestParseECSCommand:

    def test_parse_simple_command(self):
        from app.routes.ecs_manage import _parse_ecs_command
        action, params = _parse_ecs_command("aws ecs list-services --cluster my-cluster")
        assert action == "list-services"
        assert params["cluster"] == "my-cluster"

    def test_parse_list_params(self):
        from app.routes.ecs_manage import _parse_ecs_command
        action, params = _parse_ecs_command("aws ecs describe-services --cluster my --services svc1 --services svc2")
        assert action == "describe-services"
        assert params["services"] == ["svc1", "svc2"]

    def test_parse_json_value(self):
        from app.routes.ecs_manage import _parse_ecs_command
        cmd = """aws ecs run-task --cluster my --task-definition td --launch-type FARGATE --network-configuration '{"awsvpcConfiguration":{"subnets":["s1"]}}'"""
        action, params = _parse_ecs_command(cmd)
        assert action == "run-task"
        assert params["launchType"] == "FARGATE"
        assert isinstance(params["networkConfiguration"], dict)
        assert params["networkConfiguration"]["awsvpcConfiguration"]["subnets"] == ["s1"]

    def test_rejects_unsupported_action(self):
        from app.routes.ecs_manage import _parse_ecs_command
        with pytest.raises(ValueError, match="Unsupported action"):
            _parse_ecs_command("aws ecs fake-action")

    def test_rejects_non_ecs_command(self):
        from app.routes.ecs_manage import _parse_ecs_command
        with pytest.raises(ValueError, match="must start with"):
            _parse_ecs_command("aws s3 ls")

    def test_write_actions_are_present(self):
        from app.routes.ecs_manage import ECS_API_ACTIONS
        assert "run-task" in ECS_API_ACTIONS
        assert "stop-task" in ECS_API_ACTIONS
        assert "update-service" in ECS_API_ACTIONS
        assert "delete-service" in ECS_API_ACTIONS
        assert "deregister-task-definition" in ECS_API_ACTIONS

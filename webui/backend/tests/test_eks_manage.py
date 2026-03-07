import json
import pytest
from pathlib import Path

from app.services.eks_preset_manager import EKSPresetManager


@pytest.fixture
def eks_env(tmp_path):
    eks_dir = tmp_path / "eks"
    eks_dir.mkdir()

    helm_dir = eks_dir / "agent-helm"
    helm_dir.mkdir()
    (helm_dir / "manifest.json").write_text(json.dumps({
        "name": "agent-helm",
        "description": "Datadog Agent via Helm chart",
        "type": "helm",
        "built_in": True,
        "deploy_commands": [
            "helm repo add datadog https://helm.datadoghq.com --force-update",
            "helm repo update",
            "helm upgrade --install datadog-agent datadog/datadog -f datadog-values.yaml",
        ],
        "update_commands": [
            "helm repo update",
            "helm upgrade datadog-agent datadog/datadog -f datadog-values.yaml",
        ],
        "undeploy_commands": ["helm uninstall datadog-agent"],
        "files": ["datadog-values.yaml", "README.md"],
    }))
    (helm_dir / "datadog-values.yaml").write_text("datadog:\n  site: datadoghq.com\n")
    (helm_dir / "README.md").write_text("# agent-helm\n")

    op_dir = eks_dir / "agent-datadog-operator"
    op_dir.mkdir()
    (op_dir / "manifest.json").write_text(json.dumps({
        "name": "agent-datadog-operator",
        "description": "Datadog Agent via Operator",
        "type": "kubectl",
        "built_in": True,
        "deploy_commands": ["kubectl apply -f datadog-agent.yaml"],
        "update_commands": ["kubectl apply -f datadog-agent.yaml"],
        "undeploy_commands": ["kubectl delete -f datadog-agent.yaml --ignore-not-found"],
        "files": ["datadog-agent.yaml"],
    }))
    (op_dir / "datadog-agent.yaml").write_text("kind: DatadogAgent\n")

    return tmp_path


@pytest.fixture
def manager(eks_env):
    mgr = EKSPresetManager(str(eks_env))
    mgr._get_s3_manager = lambda: None
    return mgr


def test_list_presets_returns_built_in(manager):
    presets = manager.list_presets()
    names = {p["name"] for p in presets}
    assert "agent-helm" in names
    assert "agent-datadog-operator" in names
    assert len(presets) >= 2
    for p in presets:
        assert p["built_in"] is True


def test_get_preset_returns_details(manager):
    preset = manager.get_preset("agent-helm")
    assert preset is not None
    assert preset["name"] == "agent-helm"
    assert preset["type"] == "helm"
    assert "datadog-values.yaml" in preset["files"]
    assert "README.md" in preset["files"]


def test_get_preset_commands_are_strings(manager):
    preset = manager.get_preset("agent-helm")
    for cmd in preset["deploy_commands"]:
        assert isinstance(cmd, str)
    for cmd in preset["update_commands"]:
        assert isinstance(cmd, str)
    for cmd in preset["undeploy_commands"]:
        assert isinstance(cmd, str)


def test_get_preset_returns_none_for_missing(manager):
    assert manager.get_preset("nonexistent") is None


def test_get_preset_file_returns_content(manager):
    content = manager.get_preset_file("agent-helm", "datadog-values.yaml")
    assert content is not None
    assert "datadoghq.com" in content


def test_get_preset_file_returns_none_for_missing(manager):
    assert manager.get_preset_file("agent-helm", "nonexistent.yaml") is None


def test_create_preset(manager):
    result = manager.create_preset(
        name="my-custom",
        description="Test preset",
        preset_type="kubectl",
        files={"app.yaml": "apiVersion: v1\nkind: Pod\n"},
    )
    assert result is True

    preset = manager.get_preset("my-custom")
    assert preset is not None
    assert preset["name"] == "my-custom"
    assert preset["description"] == "Test preset"
    assert preset["built_in"] is False

    content = manager.get_preset_file("my-custom", "app.yaml")
    assert "apiVersion: v1" in content


def test_create_preset_fails_for_existing(manager):
    assert manager.create_preset(name="agent-helm") is False


def test_save_preset_file(manager):
    new_content = "datadog:\n  site: us5.datadoghq.com\n"
    result = manager.save_preset_file("agent-helm", "datadog-values.yaml", new_content)
    assert result is True

    content = manager.get_preset_file("agent-helm", "datadog-values.yaml")
    assert "us5.datadoghq.com" in content


def test_delete_preset_blocks_built_in(manager):
    assert manager.delete_preset("agent-helm") is False


def test_delete_custom_preset(manager):
    manager.create_preset(name="to-delete", description="tmp")
    assert manager.get_preset("to-delete") is not None

    result = manager.delete_preset("to-delete")
    assert result is True
    assert manager.get_preset("to-delete") is None


def test_clone_preset(manager):
    result = manager.clone_preset("agent-helm", "my-helm-clone")
    assert result is True

    clone = manager.get_preset("my-helm-clone")
    assert clone is not None
    assert clone["name"] == "my-helm-clone"
    assert clone["built_in"] is False
    assert "Cloned from agent-helm" in clone["description"]

    content = manager.get_preset_file("my-helm-clone", "datadog-values.yaml")
    assert content is not None
    assert "datadoghq.com" in content


def test_clone_preset_fails_for_existing_target(manager):
    assert manager.clone_preset("agent-helm", "agent-datadog-operator") is False


def test_sync_preset_to_local(manager):
    preset_dir = manager.sync_preset_to_local("agent-helm")
    assert preset_dir is not None
    assert (preset_dir / "datadog-values.yaml").exists()


def test_sync_preset_to_local_missing(manager):
    result = manager.sync_preset_to_local("nonexistent")
    assert result is None


def test_build_default_layout(manager):
    all_presets = {p["name"]: p for p in manager.list_presets()}
    layout = manager._build_default_layout(all_presets)
    assert len(layout) >= 1
    ootb_folder = next((n for n in layout if n["type"] == "folder" and n["id"] == "ootb"), None)
    assert ootb_folder is not None
    assert "agent-helm" in ootb_folder["children"]
    assert "agent-datadog-operator" in ootb_folder["children"]


def test_sync_layout_removes_deleted(manager):
    layout = [
        {"id": "ootb", "type": "folder", "name": "ootb", "children": ["agent-helm", "deleted-preset"]},
        {"id": "also-deleted", "type": "preset"},
    ]
    all_presets = {p["name"]: p for p in manager.list_presets()}
    synced = manager._sync_layout(layout, all_presets)
    ootb_folder = next(n for n in synced if n["id"] == "ootb")
    assert "deleted-preset" not in ootb_folder["children"]
    assert not any(n.get("id") == "also-deleted" for n in synced)
    assert any(n.get("id") == "agent-datadog-operator" or
               ("children" in n and "agent-datadog-operator" in n["children"]) for n in synced)

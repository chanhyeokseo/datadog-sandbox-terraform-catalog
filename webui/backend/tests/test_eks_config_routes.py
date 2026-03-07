import json

import pytest

from app.models.schemas import ResourceStatus, ResourceType, TerraformResource
from app.routes import terraform as terraform_routes


def _eks_resource(resource_id: str = "eks_custom") -> TerraformResource:
    return TerraformResource(
        id=resource_id,
        name="EKS Custom",
        type=ResourceType.EKS,
        file_path="instances/eks-custom/main.tf",
        line_start=1,
        line_end=3,
        status=ResourceStatus.ENABLED,
    )


async def _terraform_output_failure(*args, **kwargs):
    return False, ""


def _full_eks_outputs(**overrides):
    payload = {
        "enable_node_group": {"value": True},
        "node_instance_types": {"value": ["t3.medium"]},
        "node_desired_size": {"value": 2},
        "node_min_size": {"value": 1},
        "node_max_size": {"value": 4},
        "node_disk_size": {"value": 20},
        "node_capacity_type": {"value": "ON_DEMAND"},
        "enable_windows_node_group": {"value": False},
        "windows_node_instance_types": {"value": ["t3.medium"]},
        "windows_node_ami_type": {"value": "WINDOWS_FULL_2022_x86_64"},
        "windows_node_desired_size": {"value": 2},
        "windows_node_min_size": {"value": 1},
        "windows_node_max_size": {"value": 4},
        "windows_node_disk_size": {"value": 50},
        "windows_node_capacity_type": {"value": "ON_DEMAND"},
        "enable_fargate": {"value": False},
        "fargate_namespaces": {"value": ["default", "kube-system"]},
        "endpoint_public_access": {"value": True},
        "endpoint_private_access": {"value": True},
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_get_eks_config_returns_error_when_output_fails(monkeypatch, tmp_path):
    eks_dir = tmp_path / "eks-custom"
    eks_dir.mkdir()

    monkeypatch.setattr(terraform_routes.parser, "parse_all_resources", lambda: [_eks_resource()])
    monkeypatch.setattr(
        terraform_routes.runner,
        "get_resource_directory",
        lambda resource_id: eks_dir if resource_id == "eks_custom" else None,
    )
    monkeypatch.setattr(terraform_routes.runner, "output", _terraform_output_failure)
    monkeypatch.setattr(terraform_routes.parser, "get_aws_env", lambda: {})

    result = await terraform_routes.get_eks_config()

    assert result == {"error": "Failed to read terraform output for EKS resource"}


@pytest.mark.asyncio
async def test_get_eks_config_reads_terraform_output_only(monkeypatch, tmp_path):
    eks_dir = tmp_path / "eks-custom"
    eks_dir.mkdir()

    async def fake_output(*args, **kwargs):
        return True, json.dumps(_full_eks_outputs(
            enable_node_group={"value": False},
            node_instance_types={"value": ["m5.large"]},
            node_desired_size={"value": 3},
            enable_fargate={"value": True},
            fargate_namespaces={"value": ["default", "observability"]},
        ))

    monkeypatch.setattr(terraform_routes.parser, "parse_all_resources", lambda: [_eks_resource()])
    monkeypatch.setattr(
        terraform_routes.runner,
        "get_resource_directory",
        lambda resource_id: eks_dir if resource_id == "eks_custom" else None,
    )
    monkeypatch.setattr(terraform_routes.runner, "output", fake_output)
    monkeypatch.setattr(terraform_routes.parser, "get_aws_env", lambda: {})

    result = await terraform_routes.get_eks_config()

    assert result["enable_node_group"] is False
    assert result["node_instance_types"] == ["m5.large"]
    assert result["node_desired_size"] == 3
    assert result["enable_fargate"] is True
    assert result["fargate_namespaces"] == ["default", "observability"]
    assert result["endpoint_public_access"] is True


@pytest.mark.asyncio
async def test_get_eks_config_returns_error_when_outputs_missing(monkeypatch, tmp_path):
    eks_dir = tmp_path / "eks-custom"
    eks_dir.mkdir()

    async def fake_output(*args, **kwargs):
        return True, json.dumps({
            "enable_node_group": {"value": False},
            "node_instance_types": {"value": ["m5.large"]},
        })

    monkeypatch.setattr(terraform_routes.parser, "parse_all_resources", lambda: [_eks_resource()])
    monkeypatch.setattr(
        terraform_routes.runner,
        "get_resource_directory",
        lambda resource_id: eks_dir if resource_id == "eks_custom" else None,
    )
    monkeypatch.setattr(terraform_routes.runner, "output", fake_output)
    monkeypatch.setattr(terraform_routes.parser, "get_aws_env", lambda: {})

    result = await terraform_routes.get_eks_config()

    assert result["error"] == "Required EKS config outputs are missing"
    assert "node_desired_size" in result["missing_outputs"]
    assert "endpoint_private_access" in result["missing_outputs"]


@pytest.mark.asyncio
async def test_get_eks_config_falls_back_to_instances_scan(monkeypatch, tmp_path):
    instances_dir = tmp_path / "instances"
    eks_dir = instances_dir / "eks-cluster"
    eks_dir.mkdir(parents=True)
    (eks_dir / "main.tf").write_text(
        'module "eks_cluster" {\n  source = "../../modules/eks"\n}\n',
        encoding="utf-8",
    )

    async def fake_output(*args, **kwargs):
        return True, json.dumps(_full_eks_outputs())

    async def fake_init(*args, **kwargs):
        return True, ""

    monkeypatch.setattr(terraform_routes.parser, "parse_all_resources", lambda: [])
    monkeypatch.setattr(terraform_routes.parser, "instances_dir", instances_dir)
    monkeypatch.setattr(terraform_routes.runner, "ensure_terraform_init", fake_init)
    monkeypatch.setattr(terraform_routes.runner, "output", fake_output)
    monkeypatch.setattr(terraform_routes.parser, "get_aws_env", lambda: {})

    result = await terraform_routes.get_eks_config()

    assert result["enable_node_group"] is True
    assert result["node_instance_types"] == ["t3.medium"]
    assert result["endpoint_private_access"] is True


@pytest.mark.asyncio
async def test_update_eks_config_writes_to_discovered_directory(monkeypatch, tmp_path):
    eks_dir = tmp_path / "eks-custom"
    eks_dir.mkdir()

    monkeypatch.setattr(terraform_routes.parser, "parse_all_resources", lambda: [_eks_resource()])
    monkeypatch.setattr(
        terraform_routes.runner,
        "get_resource_directory",
        lambda resource_id: eks_dir if resource_id == "eks_custom" else None,
    )

    result = await terraform_routes.update_eks_config({
        "enable_node_group": True,
        "node_instance_types": ["m5.large"],
        "node_desired_size": 2,
        "node_min_size": 1,
        "node_max_size": 3,
        "node_disk_size": 40,
        "node_capacity_type": "SPOT",
    })

    content = (eks_dir / "eks-config.auto.tfvars").read_text(encoding="utf-8")

    assert result["success"] is True
    assert 'node_instance_types = ["m5.large"]' in content
    assert 'node_capacity_type  = "SPOT"' in content

import pytest
from pathlib import Path

from app.services.instance_discovery import (
    get_resource_id_for_instance,
    get_resource_type_from_dir,
    get_resource_directory_map,
)
from app.models.schemas import ResourceType


class TestGetResourceTypeFromDir:

    @pytest.mark.parametrize("dir_name,expected", [
        ("ec2-basic", ResourceType.EC2),
        ("ec2-datadog-docker", ResourceType.EC2),
        ("ec2-windows-2025", ResourceType.EC2),
        ("eks-cluster", ResourceType.EKS),
        ("ecs-ec2", ResourceType.ECS),
        ("ecs-fargate", ResourceType.ECS),
        ("ecr-apps", ResourceType.ECR),
        ("deploy-spring-boot", ResourceType.ECR),
        ("lambda-python-example", ResourceType.LAMBDA),
        ("dbm-autoconfig-postgres", ResourceType.DBM),
        ("security-group", ResourceType.SECURITY_GROUP),
        ("test-file-1", ResourceType.TEST),
        ("test-file-abc", ResourceType.TEST),
    ])
    def test_known_prefixes(self, dir_name, expected):
        assert get_resource_type_from_dir(dir_name) == expected

    def test_unknown_prefix_defaults_to_ec2(self):
        assert get_resource_type_from_dir("something-random") == ResourceType.EC2


class TestGetResourceIdForInstance:

    def test_reads_from_resource_id_file(self, tmp_path):
        inst = tmp_path / "my-instance"
        inst.mkdir()
        (inst / ".resource_id").write_text("custom_id\n")
        assert get_resource_id_for_instance(inst) == "custom_id"

    def test_parses_module_name_from_main_tf(self, tmp_path):
        inst = tmp_path / "eks-cluster"
        inst.mkdir()
        (inst / "main.tf").write_text('module "eks_cluster" {\n  source = "../../modules/eks"\n}\n')
        assert get_resource_id_for_instance(inst) == "eks_cluster"

    def test_falls_back_to_dir_name(self, tmp_path):
        inst = tmp_path / "my-resource"
        inst.mkdir()
        (inst / "main.tf").write_text("resource \"aws_instance\" \"main\" {}\n")
        assert get_resource_id_for_instance(inst) == "my_resource"

    def test_falls_back_when_no_main_tf(self, tmp_path):
        inst = tmp_path / "empty-dir"
        inst.mkdir()
        assert get_resource_id_for_instance(inst) == "empty_dir"

    def test_resource_id_file_takes_priority_over_main_tf(self, tmp_path):
        inst = tmp_path / "ec2-basic"
        inst.mkdir()
        (inst / ".resource_id").write_text("override_id")
        (inst / "main.tf").write_text('module "ec2_basic" {\n}\n')
        assert get_resource_id_for_instance(inst) == "override_id"


class TestGetResourceDirectoryMap:

    def test_maps_instances_with_main_tf(self, tmp_path):
        for name in ["ec2-basic", "eks-cluster"]:
            d = tmp_path / name
            d.mkdir()
            (d / "main.tf").write_text(f'module "{name.replace("-", "_")}" {{}}\n')
        result = get_resource_directory_map(tmp_path)
        assert result["ec2_basic"] == "ec2-basic"
        assert result["eks_cluster"] == "eks-cluster"

    def test_skips_dirs_without_main_tf(self, tmp_path):
        d = tmp_path / "no-main"
        d.mkdir()
        (d / "README.md").write_text("nothing")
        assert get_resource_directory_map(tmp_path) == {}

    def test_returns_empty_for_nonexistent_dir(self, tmp_path):
        assert get_resource_directory_map(tmp_path / "does-not-exist") == {}

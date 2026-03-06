import pytest
from pathlib import Path


@pytest.fixture
def tmp_terraform_dir(tmp_path):
    instances_dir = tmp_path / "instances"
    instances_dir.mkdir()
    return tmp_path


@pytest.fixture
def root_tfvars(tmp_terraform_dir):
    tfvars = tmp_terraform_dir / "terraform.tfvars"
    return tfvars

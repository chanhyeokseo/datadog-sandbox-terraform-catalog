import os
import pytest
from unittest.mock import patch
from pathlib import Path

from app.services.terraform_runner import TerraformRunner


class TestGetResourceDirectory:

    def test_resolves_known_resource(self, tmp_terraform_dir):
        inst = tmp_terraform_dir / "instances" / "ec2-basic"
        inst.mkdir(parents=True)
        (inst / "main.tf").write_text('module "ec2_basic" {}\n')
        runner = TerraformRunner(str(tmp_terraform_dir))
        result = runner.get_resource_directory("ec2_basic")
        assert result is not None
        assert result.name == "ec2-basic"

    def test_returns_none_for_unknown_resource(self, tmp_terraform_dir):
        runner = TerraformRunner(str(tmp_terraform_dir))
        assert runner.get_resource_directory("nonexistent") is None


class TestBuildEnv:

    def test_returns_none_when_no_extra(self, tmp_terraform_dir):
        runner = TerraformRunner(str(tmp_terraform_dir))
        assert runner._build_env(None) is None
        assert runner._build_env({}) is None

    def test_merges_env_extra_with_os_environ(self, tmp_terraform_dir):
        runner = TerraformRunner(str(tmp_terraform_dir))
        result = runner._build_env({"CUSTOM_VAR": "value"})
        assert result["CUSTOM_VAR"] == "value"
        assert "PATH" in result

    def test_extra_overrides_os_environ(self, tmp_terraform_dir):
        runner = TerraformRunner(str(tmp_terraform_dir))
        result = runner._build_env({"PATH": "/custom"})
        assert result["PATH"] == "/custom"


class TestParseWarmupLine:

    @pytest.fixture
    def runner(self, tmp_terraform_dir):
        return TerraformRunner(str(tmp_terraform_dir))

    def test_initializing_plugins(self, runner):
        runner._parse_warmup_line("Initializing provider plugins...")
        assert runner._warmup_progress == 10

    def test_finding_version(self, runner):
        runner._parse_warmup_line("- Finding latest version of hashicorp/aws...")
        assert runner._warmup_progress == 20

    def test_installing_provider(self, runner):
        runner._parse_warmup_line("- Installing hashicorp/aws v5.0.0...")
        assert runner._warmup_progress == 40

    def test_installed_provider(self, runner):
        runner._parse_warmup_line("- Installed hashicorp/aws v5.0.0")
        assert runner._warmup_progress == 95

    def test_unrelated_line_no_change(self, runner):
        runner._warmup_progress = 0
        runner._parse_warmup_line("Some random terraform output")
        assert runner._warmup_progress == 0


class TestGetCacheStatus:

    def test_default_not_ready(self, tmp_terraform_dir):
        runner = TerraformRunner(str(tmp_terraform_dir))
        status = runner.get_cache_status()
        assert status["ready"] is False
        assert status["progress"] == 0

    def test_reflects_progress(self, tmp_terraform_dir):
        runner = TerraformRunner(str(tmp_terraform_dir))
        runner._warmup_progress = 50
        runner._warmup_message = "halfway"
        status = runner.get_cache_status()
        assert status["progress"] == 50
        assert status["message"] == "halfway"

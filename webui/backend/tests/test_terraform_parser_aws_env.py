import os
import pytest
from unittest.mock import patch
from app.services.terraform_parser import TerraformParser


class TestGetAwsEnvTfVarAwsProfile:

    def test_sets_tf_var_when_aws_profile_present(self, tmp_terraform_dir):
        parser = TerraformParser(str(tmp_terraform_dir))
        with patch.dict(os.environ, {"AWS_PROFILE": "my-profile"}, clear=False):
            result = parser.get_aws_env()
        assert result["TF_VAR_aws_profile"] == "my-profile"
        assert result["AWS_PROFILE"] == "my-profile"

    def test_omits_tf_var_when_aws_profile_absent(self, tmp_terraform_dir):
        parser = TerraformParser(str(tmp_terraform_dir))
        env = {k: v for k, v in os.environ.items() if k != "AWS_PROFILE"}
        with patch.dict(os.environ, env, clear=True):
            result = parser.get_aws_env()
        assert "TF_VAR_aws_profile" not in result
        assert "AWS_PROFILE" not in result

    def test_omits_tf_var_when_aws_profile_empty(self, tmp_terraform_dir):
        parser = TerraformParser(str(tmp_terraform_dir))
        with patch.dict(os.environ, {"AWS_PROFILE": ""}, clear=False):
            result = parser.get_aws_env()
        assert "TF_VAR_aws_profile" not in result

    def test_reads_region_from_tfvars(self, tmp_terraform_dir, root_tfvars):
        root_tfvars.write_text('region = "us-west-2"\n')
        parser = TerraformParser(str(tmp_terraform_dir))
        env = {k: v for k, v in os.environ.items() if k not in ("AWS_PROFILE", "AWS_REGION")}
        with patch.dict(os.environ, env, clear=True):
            result = parser.get_aws_env()
        assert result["AWS_REGION"] == "us-west-2"

    def test_env_region_overrides_tfvars_region(self, tmp_terraform_dir, root_tfvars):
        root_tfvars.write_text('region = "us-west-2"\n')
        parser = TerraformParser(str(tmp_terraform_dir))
        env = {k: v for k, v in os.environ.items() if k != "AWS_PROFILE"}
        env["AWS_REGION"] = "eu-west-1"
        with patch.dict(os.environ, env, clear=True):
            result = parser.get_aws_env()
        assert result["AWS_REGION"] == "eu-west-1"

    def test_reads_credentials_from_tfvars(self, tmp_terraform_dir, root_tfvars):
        root_tfvars.write_text(
            'aws_access_key_id = "AKIATEST"\n'
            'aws_secret_access_key = "secret123"\n'
        )
        parser = TerraformParser(str(tmp_terraform_dir))
        env = {k: v for k, v in os.environ.items()
               if k not in ("AWS_PROFILE", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")}
        with patch.dict(os.environ, env, clear=True):
            result = parser.get_aws_env()
        assert result["AWS_ACCESS_KEY_ID"] == "AKIATEST"
        assert result["AWS_SECRET_ACCESS_KEY"] == "secret123"

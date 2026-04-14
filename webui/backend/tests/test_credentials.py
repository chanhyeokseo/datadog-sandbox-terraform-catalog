import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from botocore.exceptions import ProfileNotFound, ClientError
from fastapi import HTTPException

from app.routes.terraform import _is_credential_error, check_credentials, get_resources


class TestIsCredentialError:

    @pytest.mark.parametrize("msg", [
        "Token has expired",
        "Unable to locate credentials",
        "No credentials found",
        "expired token in SSO cache",
    ])
    def test_detects_credential_errors(self, msg):
        assert _is_credential_error(Exception(msg)) is True

    @pytest.mark.parametrize("msg", [
        "Resource not found",
        "Internal server error",
        "timeout",
    ])
    def test_ignores_unrelated_errors(self, msg):
        assert _is_credential_error(Exception(msg)) is False


class TestCheckCredentialsProfileNotFound:

    @pytest.mark.asyncio
    async def test_returns_401_with_profile_not_found(self):
        with patch("app.routes.terraform.parser") as mock_parser, \
             patch("app.routes.terraform.boto3") as mock_boto3, \
             patch.dict(os.environ, {"AWS_PROFILE": "bad-profile"}):
            mock_parser.get_aws_env.return_value = {}
            mock_boto3.client.side_effect = ProfileNotFound(profile="bad-profile")

            with pytest.raises(HTTPException) as exc_info:
                await check_credentials()

            assert exc_info.value.status_code == 401
            detail = exc_info.value.detail
            assert detail["error_type"] == "profile_not_found"
            assert detail["aws_profile"] == "bad-profile"
            assert "bad-profile" in detail["message"]

    @pytest.mark.asyncio
    async def test_returns_401_with_sso_command_on_expired_credentials(self):
        with patch("app.routes.terraform.parser") as mock_parser, \
             patch("app.routes.terraform.boto3") as mock_boto3, \
             patch.dict(os.environ, {"AWS_PROFILE": "my-sso-profile"}):
            mock_parser.get_aws_env.return_value = {}
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            mock_client.get_caller_identity.side_effect = Exception("Token has expired")

            with pytest.raises(HTTPException) as exc_info:
                await check_credentials()

            assert exc_info.value.status_code == 401
            detail = exc_info.value.detail
            assert detail["aws_profile"] == "my-sso-profile"
            assert detail["sso_command"] == "aws sso login --profile=my-sso-profile"

    @pytest.mark.asyncio
    async def test_returns_generic_sso_command_without_profile(self):
        env = {k: v for k, v in os.environ.items() if k != "AWS_PROFILE"}
        with patch("app.routes.terraform.parser") as mock_parser, \
             patch("app.routes.terraform.boto3") as mock_boto3, \
             patch.dict(os.environ, env, clear=True):
            mock_parser.get_aws_env.return_value = {}
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            mock_client.get_caller_identity.side_effect = Exception("No credentials")

            with pytest.raises(HTTPException) as exc_info:
                await check_credentials()

            detail = exc_info.value.detail
            assert detail["aws_profile"] == ""
            assert detail["sso_command"] == "aws sso login"

    @pytest.mark.asyncio
    async def test_returns_valid_on_success(self):
        with patch("app.routes.terraform.parser") as mock_parser, \
             patch("app.routes.terraform.boto3") as mock_boto3:
            mock_parser.get_aws_env.return_value = {"AWS_REGION": "us-east-1"}
            mock_client = MagicMock()
            mock_boto3.client.return_value = mock_client
            mock_client.get_caller_identity.return_value = {
                "Account": "123456789012",
                "Arn": "arn:aws:iam::123456789012:user/test",
            }

            result = await check_credentials()

            assert result["valid"] is True
            assert result["account"] == "123456789012"
            mock_boto3.client.assert_called_once_with("sts", region_name="us-east-1")


class TestGetResourcesProfileNotFound:

    @pytest.mark.asyncio
    async def test_returns_401_when_profile_not_found(self):
        with patch("app.routes.terraform.parser") as mock_parser, \
             patch.dict(os.environ, {"AWS_PROFILE": "bad-profile"}):
            mock_parser.parse_all_resources.side_effect = ProfileNotFound(profile="bad-profile")

            with pytest.raises(HTTPException) as exc_info:
                await get_resources()

            assert exc_info.value.status_code == 401
            detail = exc_info.value.detail
            assert detail["error_type"] == "profile_not_found"
            assert detail["aws_profile"] == "bad-profile"

    @pytest.mark.asyncio
    async def test_returns_401_with_sso_command_on_credential_error(self):
        with patch("app.routes.terraform.parser") as mock_parser, \
             patch.dict(os.environ, {"AWS_PROFILE": "my-profile"}):
            mock_parser.parse_all_resources.side_effect = Exception("Token has expired")

            with pytest.raises(HTTPException) as exc_info:
                await get_resources()

            assert exc_info.value.status_code == 401
            detail = exc_info.value.detail
            assert detail["sso_command"] == "aws sso login --profile=my-profile"

    @pytest.mark.asyncio
    async def test_returns_500_on_generic_error(self):
        with patch("app.routes.terraform.parser") as mock_parser:
            mock_parser.parse_all_resources.side_effect = Exception("Something broke")

            with pytest.raises(HTTPException) as exc_info:
                await get_resources()

            assert exc_info.value.status_code == 500

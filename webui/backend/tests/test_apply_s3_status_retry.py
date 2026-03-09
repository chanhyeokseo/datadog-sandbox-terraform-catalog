import asyncio
from dataclasses import dataclass, field
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import ResourceStatus
from app.routes.terraform import _run_apply_background


@dataclass
class FakeOperation:
    resource_id: str
    operation: str = "apply"
    status: str = "running"
    output: List[str] = field(default_factory=list)
    exit_code: Optional[int] = None


def _make_stream_apply(exit_code=0):
    async def stream_apply(**kwargs):
        yield "Apply complete!\n"
        yield f"__TF_EXIT__:{exit_code}\n"
    return stream_apply


class TestApplyS3StatusRetry:

    @pytest.mark.asyncio
    async def test_retries_s3_status_after_credential_refresh_on_disabled(self):
        op = FakeOperation(resource_id="security_group")
        mock_res_dir = MagicMock()
        mock_res_dir.name = "security-group"

        invalidate_calls = []

        def fake_invalidate(dir_name=None):
            call_index = len(invalidate_calls)
            invalidate_calls.append(dir_name)
            if call_index == 0:
                return ResourceStatus.DISABLED
            return ResourceStatus.ENABLED

        with patch("app.routes.terraform.runner") as mock_runner, \
             patch("app.routes.terraform.parser") as mock_parser, \
             patch("app.routes.terraform.credential_manager") as mock_cred, \
             patch("app.routes.terraform.get_resource_lock", return_value=asyncio.Lock()):
            mock_runner.stream_apply = _make_stream_apply(exit_code=0)
            mock_runner.get_resource_directory.return_value = mock_res_dir
            mock_parser.invalidate_s3_status.side_effect = fake_invalidate
            mock_cred.try_refresh_credentials.return_value = True

            await _run_apply_background(op, auto_approve=True, var_files=None, aws_env=None)

            assert op.status == "completed"
            assert op.exit_code == 0
            assert len(invalidate_calls) == 2
            assert invalidate_calls[0] == "security-group"
            assert invalidate_calls[1] == "security-group"
            mock_cred.try_refresh_credentials.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_retry_when_s3_status_is_enabled(self):
        op = FakeOperation(resource_id="ec2_basic")
        mock_res_dir = MagicMock()
        mock_res_dir.name = "ec2-basic"

        def fake_invalidate(dir_name=None):
            return ResourceStatus.ENABLED

        with patch("app.routes.terraform.runner") as mock_runner, \
             patch("app.routes.terraform.parser") as mock_parser, \
             patch("app.routes.terraform.credential_manager") as mock_cred, \
             patch("app.routes.terraform.get_resource_lock", return_value=asyncio.Lock()):
            mock_runner.stream_apply = _make_stream_apply(exit_code=0)
            mock_runner.get_resource_directory.return_value = mock_res_dir
            mock_parser.invalidate_s3_status.side_effect = fake_invalidate

            await _run_apply_background(op, auto_approve=True, var_files=None, aws_env=None)

            assert op.status == "completed"
            mock_cred.try_refresh_credentials.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_retry_when_apply_fails(self):
        op = FakeOperation(resource_id="security_group")

        with patch("app.routes.terraform.runner") as mock_runner, \
             patch("app.routes.terraform.parser") as mock_parser, \
             patch("app.routes.terraform.credential_manager") as mock_cred, \
             patch("app.routes.terraform.get_resource_lock", return_value=asyncio.Lock()):
            mock_runner.stream_apply = _make_stream_apply(exit_code=1)

            await _run_apply_background(op, auto_approve=True, var_files=None, aws_env=None)

            assert op.status == "failed"
            assert op.exit_code == 1
            mock_parser.invalidate_s3_status.assert_not_called()
            mock_cred.try_refresh_credentials.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_second_retry_when_credential_refresh_fails(self):
        op = FakeOperation(resource_id="security_group")
        mock_res_dir = MagicMock()
        mock_res_dir.name = "security-group"

        def fake_invalidate(dir_name=None):
            return ResourceStatus.DISABLED

        with patch("app.routes.terraform.runner") as mock_runner, \
             patch("app.routes.terraform.parser") as mock_parser, \
             patch("app.routes.terraform.credential_manager") as mock_cred, \
             patch("app.routes.terraform.get_resource_lock", return_value=asyncio.Lock()):
            mock_runner.stream_apply = _make_stream_apply(exit_code=0)
            mock_runner.get_resource_directory.return_value = mock_res_dir
            mock_parser.invalidate_s3_status.side_effect = fake_invalidate
            mock_cred.try_refresh_credentials.return_value = False

            await _run_apply_background(op, auto_approve=True, var_files=None, aws_env=None)

            assert op.status == "completed"
            mock_cred.try_refresh_credentials.assert_called_once()
            assert mock_parser.invalidate_s3_status.call_count == 1


class TestInvalidateS3StatusReturnValue:

    @pytest.fixture
    def parser(self, tmp_terraform_dir):
        from app.services.terraform_parser import TerraformParser
        return TerraformParser(str(tmp_terraform_dir))

    def test_returns_none_when_dir_name_is_none(self, parser):
        with patch.object(parser, "build_s3_status_cache"):
            result = parser.invalidate_s3_status(None)
            assert result is None

    def test_returns_status_for_specific_dir(self, parser):
        parser._s3_status_cache = {}
        with patch.object(parser, "_fetch_single_s3_status", return_value=ResourceStatus.ENABLED):
            result = parser.invalidate_s3_status("ec2-basic")
            assert result == ResourceStatus.ENABLED
            assert parser._s3_status_cache["ec2-basic"] == ResourceStatus.ENABLED

    def test_returns_disabled_on_fetch_failure(self, parser):
        parser._s3_status_cache = {}
        with patch.object(parser, "_fetch_single_s3_status", return_value=ResourceStatus.DISABLED):
            result = parser.invalidate_s3_status("security-group")
            assert result == ResourceStatus.DISABLED

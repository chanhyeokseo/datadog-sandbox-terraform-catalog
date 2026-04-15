import json
import os
import time
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from botocore.exceptions import ClientError

from app.services.credential_manager import (
    CredentialManager,
    SSOConfig,
    STS_CREDENTIAL_LIFETIME,
    CREDENTIAL_EXPIRY_BUFFER,
)


@pytest.fixture
def sso_config():
    return SSOConfig(
        start_url="https://my-sso.awsapps.com/start",
        sso_region="us-east-1",
        account_id="123456789012",
        role_name="MyRole",
        session_name="my-session",
    )


@pytest.fixture
def sso_cache_dir(tmp_path):
    cache_dir = tmp_path / "sso" / "cache"
    cache_dir.mkdir(parents=True)
    return cache_dir


@pytest.fixture
def manager(sso_cache_dir):
    with patch("app.services.credential_manager.AWS_SSO_CACHE_DIR", sso_cache_dir):
        mgr = CredentialManager()
        yield mgr


def _write_cache(manager, sso_config, expires_in=3600,
                 refresh_token="rt-abc", client_id="cid", client_secret="csec"):
    manager._write_sso_cache(
        sso_config, "at-xyz", expires_in,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
    )


class TestStsAgeTracking:

    def test_initial_sts_age_is_none(self, manager):
        assert manager._get_sts_age() is None

    def test_sts_age_after_set(self, manager):
        manager._sts_credentials_obtained_at = time.time() - 100
        age = manager._get_sts_age()
        assert age is not None
        assert 99 <= age <= 102

    def test_is_sts_expiring_soon_false_when_fresh(self, manager):
        manager._sts_credentials_obtained_at = time.time()
        assert manager._is_sts_expiring_soon() is False

    def test_is_sts_expiring_soon_true_near_expiry(self, manager):
        manager._sts_credentials_obtained_at = (
            time.time() - STS_CREDENTIAL_LIFETIME + CREDENTIAL_EXPIRY_BUFFER - 10
        )
        assert manager._is_sts_expiring_soon() is True

    def test_is_sts_expiring_soon_false_when_untracked(self, manager):
        assert manager._is_sts_expiring_soon() is False


class TestGetCredentialHealthStsProactive:

    def test_returns_expiring_soon_when_sts_old(self, manager):
        manager._sts_credentials_obtained_at = (
            time.time() - STS_CREDENTIAL_LIFETIME + CREDENTIAL_EXPIRY_BUFFER - 10
        )
        with patch.object(manager, "get_sso_config", return_value=MagicMock()):
            result = manager.get_credential_health()
        assert result["status"] == "expiring_soon"
        assert "sts_age" in result

    def test_skips_sts_check_when_not_sso(self, manager):
        manager._sts_credentials_obtained_at = time.time() - 99999
        with patch.object(manager, "get_sso_config", return_value=None), \
             patch("app.services.credential_manager.boto3") as mock_boto:
            mock_sts = MagicMock()
            mock_boto.client.return_value = mock_sts
            mock_sts.get_caller_identity.return_value = {"Account": "123", "Arn": "arn"}
            result = manager.get_credential_health()
        assert result["status"] == "valid"

    def test_includes_sts_age_in_valid_response(self, manager):
        manager._sts_credentials_obtained_at = time.time() - 300
        with patch.object(manager, "get_sso_config", return_value=None), \
             patch("app.services.credential_manager.boto3") as mock_boto:
            mock_sts = MagicMock()
            mock_boto.client.return_value = mock_sts
            mock_sts.get_caller_identity.return_value = {"Account": "123", "Arn": "arn"}
            result = manager.get_credential_health()
        assert result["status"] == "valid"
        assert 299 <= result["sts_age"] <= 302


class TestSsoCacheDiagnostics:

    def test_no_sso_config(self, manager):
        with patch.object(manager, "get_sso_config", return_value=None):
            diag = manager.get_sso_cache_diagnostics()
        assert diag["available"] is False
        assert diag["reason"] == "no_sso_config"

    def test_cache_file_missing(self, manager, sso_config):
        with patch.object(manager, "get_sso_config", return_value=sso_config):
            diag = manager.get_sso_cache_diagnostics()
        assert diag["available"] is False
        assert diag["reason"] == "cache_file_missing"

    def test_full_cache_with_refresh_token(self, manager, sso_config):
        with patch.object(manager, "get_sso_config", return_value=sso_config):
            _write_cache(manager, sso_config, expires_in=3600)
            diag = manager.get_sso_cache_diagnostics()
        assert diag["available"] is True
        assert diag["has_refresh_token"] is True
        assert diag["has_client_id"] is True
        assert diag["has_client_secret"] is True
        assert diag["refresh_capable"] is True
        assert diag["sso_token_expired"] is False
        assert 3590 <= diag["sso_token_remaining_seconds"] <= 3601

    def test_cache_without_refresh_token(self, manager, sso_config):
        with patch.object(manager, "get_sso_config", return_value=sso_config):
            _write_cache(manager, sso_config, refresh_token="", client_id="", client_secret="")
            diag = manager.get_sso_cache_diagnostics()
        assert diag["available"] is True
        assert diag["has_refresh_token"] is False
        assert diag["refresh_capable"] is False

    def test_includes_sts_age(self, manager, sso_config):
        manager._sts_credentials_obtained_at = time.time() - 500
        with patch.object(manager, "get_sso_config", return_value=sso_config):
            _write_cache(manager, sso_config)
            diag = manager.get_sso_cache_diagnostics()
        assert 499 <= diag["sts_age_seconds"] <= 502
        assert 3098 <= diag["sts_remaining_seconds"] <= 3101

    def test_expired_sso_token(self, manager, sso_config):
        with patch.object(manager, "get_sso_config", return_value=sso_config):
            _write_cache(manager, sso_config, expires_in=-100)
            diag = manager.get_sso_cache_diagnostics()
        assert diag["sso_token_expired"] is True


class TestTryRefreshSsoTokenLogging:

    def test_logs_warning_when_no_refresh_token(self, manager, sso_config, caplog):
        with patch.object(manager, "get_sso_config", return_value=sso_config):
            _write_cache(manager, sso_config, refresh_token="", client_id="cid", client_secret="csec")
        import logging
        with caplog.at_level(logging.WARNING):
            result = manager._try_refresh_sso_token(sso_config)
        assert result is False
        assert "refreshToken=False" in caplog.text

    def test_logs_warning_when_no_client_id(self, manager, sso_config, caplog):
        with patch.object(manager, "get_sso_config", return_value=sso_config):
            _write_cache(manager, sso_config, refresh_token="rt", client_id="", client_secret="csec")
        import logging
        with caplog.at_level(logging.WARNING):
            result = manager._try_refresh_sso_token(sso_config)
        assert result is False
        assert "clientId=False" in caplog.text

    def test_logs_info_when_no_cache_file(self, manager, sso_config, caplog):
        import logging
        with caplog.at_level(logging.INFO):
            result = manager._try_refresh_sso_token(sso_config)
        assert result is False
        assert "no cache file found" in caplog.text


class TestPollSsoTokenRefreshTokenLogging:

    def test_logs_warning_when_no_refresh_token(self, manager, sso_config, caplog):
        session = manager.start_sso_login.__wrapped__ if hasattr(manager.start_sso_login, '__wrapped__') else None

        from app.services.credential_manager import SSOSession
        test_session = SSOSession(
            session_id="test-sid",
            client_id="cid",
            client_secret="csec",
            device_code="dc",
            verification_uri="https://verify",
            user_code="CODE",
            expires_at=time.time() + 600,
            interval=5,
            sso_region="us-east-1",
            start_url="https://my-sso.awsapps.com/start",
            account_id="123456789012",
            role_name="MyRole",
        )
        manager._sso_sessions["test-sid"] = test_session

        mock_oidc = MagicMock()
        mock_oidc.create_token.return_value = {
            "accessToken": "at-new",
            "expiresIn": 3600,
        }
        mock_oidc.exceptions = MagicMock()
        mock_sso = MagicMock()
        mock_sso.get_role_credentials.return_value = {
            "roleCredentials": {
                "accessKeyId": "AKIA",
                "secretAccessKey": "secret",
                "sessionToken": "token",
            }
        }

        import logging
        with patch.object(manager, "get_sso_config", return_value=sso_config), \
             patch("app.services.credential_manager.boto3") as mock_boto, \
             patch.dict(os.environ, {}, clear=False), \
             caplog.at_level(logging.WARNING):
            mock_boto.client.side_effect = lambda svc, **kw: mock_oidc if svc == "sso-oidc" else mock_sso
            manager.poll_sso_token("test-sid")
        assert "AWS did not return a refresh token" in caplog.text

    def test_logs_info_when_refresh_token_present(self, manager, sso_config, caplog):
        from app.services.credential_manager import SSOSession
        test_session = SSOSession(
            session_id="test-sid2",
            client_id="cid",
            client_secret="csec",
            device_code="dc",
            verification_uri="https://verify",
            user_code="CODE",
            expires_at=time.time() + 600,
            interval=5,
            sso_region="us-east-1",
            start_url="https://my-sso.awsapps.com/start",
            account_id="123456789012",
            role_name="MyRole",
        )
        manager._sso_sessions["test-sid2"] = test_session

        mock_oidc = MagicMock()
        mock_oidc.create_token.return_value = {
            "accessToken": "at-new",
            "expiresIn": 28800,
            "refreshToken": "rt-new",
        }
        mock_oidc.exceptions = MagicMock()
        mock_sso = MagicMock()
        mock_sso.get_role_credentials.return_value = {
            "roleCredentials": {
                "accessKeyId": "AKIA",
                "secretAccessKey": "secret",
                "sessionToken": "token",
            }
        }

        import logging
        with patch.object(manager, "get_sso_config", return_value=sso_config), \
             patch("app.services.credential_manager.boto3") as mock_boto, \
             patch.dict(os.environ, {}, clear=False), \
             caplog.at_level(logging.INFO):
            mock_boto.client.side_effect = lambda svc, **kw: mock_oidc if svc == "sso-oidc" else mock_sso
            manager.poll_sso_token("test-sid2")
        assert "refreshToken=present" in caplog.text
        assert "AWS did not return a refresh token" not in caplog.text


class TestTryRefreshCredentialsSetsTimestamp:

    def test_sets_sts_obtained_at_on_success(self, manager, sso_config):
        with patch.object(manager, "get_sso_config", return_value=sso_config):
            _write_cache(manager, sso_config, expires_in=3600)

        mock_sso = MagicMock()
        mock_sso.get_role_credentials.return_value = {
            "roleCredentials": {
                "accessKeyId": "AKIA",
                "secretAccessKey": "secret",
                "sessionToken": "token",
            }
        }

        before = time.time()
        with patch.object(manager, "get_sso_config", return_value=sso_config), \
             patch("app.services.credential_manager.boto3") as mock_boto, \
             patch.dict(os.environ, {}, clear=False):
            mock_boto.client.return_value = mock_sso
            result = manager.try_refresh_credentials()

        assert result is True
        assert manager._sts_credentials_obtained_at >= before

    def test_does_not_set_timestamp_on_failure(self, manager, sso_config):
        with patch.object(manager, "get_sso_config", return_value=sso_config):
            _write_cache(manager, sso_config, expires_in=3600)

        mock_sso = MagicMock()
        mock_sso.get_role_credentials.side_effect = ClientError(
            {"Error": {"Code": "UnauthorizedException", "Message": "expired"}},
            "GetRoleCredentials",
        )

        with patch.object(manager, "get_sso_config", return_value=sso_config), \
             patch("app.services.credential_manager.boto3") as mock_boto, \
             patch.dict(os.environ, {}, clear=False):
            mock_boto.client.return_value = mock_sso
            result = manager.try_refresh_credentials()

        assert result is False
        assert manager._sts_credentials_obtained_at == 0.0

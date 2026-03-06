import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError, ProfileNotFound

from app.services.key_manager import ParameterStoreKeyManager


class TestParameterStoreKeyManagerInit:

    def test_sets_client_none_on_profile_not_found(self):
        with patch("app.services.key_manager.boto3") as mock_boto3:
            mock_boto3.client.side_effect = ProfileNotFound(profile="bad")
            mgr = ParameterStoreKeyManager()
        assert mgr.ssm_client is None

    def test_sets_client_none_on_generic_error(self):
        with patch("app.services.key_manager.boto3") as mock_boto3:
            mock_boto3.client.side_effect = RuntimeError("connection failed")
            mgr = ParameterStoreKeyManager()
        assert mgr.ssm_client is None

    def test_sets_client_on_success(self):
        with patch("app.services.key_manager.boto3") as mock_boto3:
            mock_boto3.client.return_value = MagicMock()
            mgr = ParameterStoreKeyManager()
        assert mgr.ssm_client is not None


class TestRequireClient:

    def test_raises_when_client_is_none(self):
        with patch("app.services.key_manager.boto3") as mock_boto3:
            mock_boto3.client.side_effect = ProfileNotFound(profile="bad")
            mgr = ParameterStoreKeyManager()

        with pytest.raises(ClientError) as exc_info:
            mgr._require_client()
        assert "ServiceUnavailable" in str(exc_info.value)

    def test_passes_when_client_exists(self):
        with patch("app.services.key_manager.boto3") as mock_boto3:
            mock_boto3.client.return_value = MagicMock()
            mgr = ParameterStoreKeyManager()
        mgr._require_client()


class TestMethodsGuardedByRequireClient:

    @pytest.fixture
    def broken_manager(self):
        with patch("app.services.key_manager.boto3") as mock_boto3:
            mock_boto3.client.side_effect = ProfileNotFound(profile="bad")
            return ParameterStoreKeyManager()

    @pytest.mark.parametrize("method,args", [
        ("upload_key", ("k", "content")),
        ("get_key", ("k",)),
        ("list_keys", ()),
        ("delete_key", ("k",)),
        ("key_exists", ("k",)),
        ("get_key_info", ("k",)),
        ("update_key_description", ("k", "desc")),
    ])
    def test_raises_client_error(self, broken_manager, method, args):
        with pytest.raises(ClientError):
            getattr(broken_manager, method)(*args)

import os

import pytest

from app.routes import eks_manage


@pytest.mark.asyncio
async def test_blocked_when_expired_and_refresh_fails(monkeypatch):
    monkeypatch.setattr(
        eks_manage.credential_manager,
        "get_credential_health",
        lambda: {"status": "expired", "sso_configured": True},
    )
    monkeypatch.setattr(
        eks_manage.credential_manager,
        "try_refresh_credentials",
        lambda: False,
    )
    monkeypatch.setattr(
        eks_manage.credential_manager,
        "get_aws_profile",
        lambda: "myprofile",
    )
    msg = await eks_manage._eks_aws_credentials_error_message()
    assert msg is not None
    assert "aws sso login --profile=myprofile" in msg


@pytest.mark.asyncio
async def test_ok_when_valid_and_sso_cache_exists(monkeypatch):
    monkeypatch.setattr(
        eks_manage.credential_manager,
        "get_credential_health",
        lambda: {"status": "valid", "sso_configured": True},
    )
    monkeypatch.setattr(eks_manage, "_sso_cache_file_exists", lambda: True)
    assert await eks_manage._eks_aws_credentials_error_message() is None


@pytest.mark.asyncio
async def test_ok_when_expiring_soon_and_sso_cache_exists(monkeypatch):
    monkeypatch.setattr(
        eks_manage.credential_manager,
        "get_credential_health",
        lambda: {"status": "expiring_soon", "sso_configured": True},
    )
    monkeypatch.setattr(eks_manage, "_sso_cache_file_exists", lambda: True)
    assert await eks_manage._eks_aws_credentials_error_message() is None


@pytest.mark.asyncio
async def test_ok_after_refresh_from_expired(monkeypatch):
    calls = {"n": 0}

    def health_seq():
        calls["n"] += 1
        if calls["n"] == 1:
            return {"status": "expired", "sso_configured": True}
        return {"status": "valid", "sso_configured": True}

    monkeypatch.setattr(
        eks_manage.credential_manager,
        "get_credential_health",
        health_seq,
    )
    monkeypatch.setattr(
        eks_manage.credential_manager,
        "try_refresh_credentials",
        lambda: True,
    )
    monkeypatch.setattr(eks_manage, "_sso_cache_file_exists", lambda: True)
    assert await eks_manage._eks_aws_credentials_error_message() is None


@pytest.mark.asyncio
async def test_blocked_when_sso_cache_file_missing(monkeypatch):
    monkeypatch.setattr(
        eks_manage.credential_manager,
        "get_credential_health",
        lambda: {"status": "valid", "sso_configured": True},
    )
    monkeypatch.setattr(eks_manage, "_sso_cache_file_exists", lambda: False)
    monkeypatch.setattr(
        eks_manage.credential_manager,
        "get_aws_profile",
        lambda: "myprofile",
    )
    msg = await eks_manage._eks_aws_credentials_error_message()
    assert msg is not None
    assert "logged out" in msg


@pytest.mark.asyncio
async def test_ok_when_no_sso_configured(monkeypatch):
    monkeypatch.setattr(
        eks_manage.credential_manager,
        "get_credential_health",
        lambda: {"status": "valid", "sso_configured": False},
    )
    assert await eks_manage._eks_aws_credentials_error_message() is None


@pytest.mark.asyncio
async def test_blocked_when_refresh_succeeds_but_health_still_bad(monkeypatch):
    monkeypatch.setattr(
        eks_manage.credential_manager,
        "get_credential_health",
        lambda: {"status": "expired", "sso_configured": True},
    )
    monkeypatch.setattr(
        eks_manage.credential_manager,
        "try_refresh_credentials",
        lambda: True,
    )
    monkeypatch.setattr(
        eks_manage.credential_manager,
        "get_aws_profile",
        lambda: "",
    )
    msg = await eks_manage._eks_aws_credentials_error_message()
    assert msg is not None


@pytest.mark.asyncio
async def test_setup_kubeconfig_fails_when_outputs_missing_cluster(monkeypatch, tmp_path):
    async def empty_cluster(*args, **kwargs):
        return {}

    monkeypatch.setattr(eks_manage, "_get_cluster_info_async", empty_cluster)
    monkeypatch.setattr(eks_manage, "_get_my_cluster_name", lambda: None)

    ok, _cluster, lines = await eks_manage._setup_kubeconfig("eks_cluster", tmp_path)
    assert ok is False
    joined = "".join(lines)
    assert "Could not resolve EKS cluster name" in joined
    assert eks_manage.EXIT_SENTINEL_PREFIX in joined


@pytest.mark.asyncio
async def test_setup_kubeconfig_fails_without_eks_resource_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(eks_manage, "_get_my_cluster_name", lambda: None)

    ok, _cluster, lines = await eks_manage._setup_kubeconfig(None, None)
    assert ok is False
    assert "No EKS Terraform instance directory" in "".join(lines)

import asyncio
import configparser
import hashlib
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

AWS_CONFIG_PATH = Path(os.environ.get("AWS_CONFIG_FILE", os.path.expanduser("~/.aws/config")))
AWS_SSO_CACHE_DIR = Path(os.path.expanduser("~/.aws/sso/cache"))

CREDENTIAL_HEALTH_INTERVAL = 300
CREDENTIAL_EXPIRY_BUFFER = 600
STS_CREDENTIAL_LIFETIME = 3600


class SSOSession:
    def __init__(self, session_id: str, client_id: str, client_secret: str,
                 device_code: str, verification_uri: str, user_code: str,
                 expires_at: float, interval: int, sso_region: str,
                 start_url: str, account_id: str, role_name: str):
        self.session_id = session_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.device_code = device_code
        self.verification_uri = verification_uri
        self.user_code = user_code
        self.expires_at = expires_at
        self.interval = interval
        self.sso_region = sso_region
        self.start_url = start_url
        self.account_id = account_id
        self.role_name = role_name
        self.status = "pending"


class SSOConfig:
    def __init__(self, start_url: str, sso_region: str, account_id: str,
                 role_name: str, session_name: str = ""):
        self.start_url = start_url
        self.sso_region = sso_region
        self.account_id = account_id
        self.role_name = role_name
        self.session_name = session_name


class CredentialManager:
    def __init__(self):
        self._sso_sessions: Dict[str, SSOSession] = {}
        self._original_profile: str = os.environ.get("AWS_PROFILE", "")
        self._sts_credentials_obtained_at: float = 0.0

    def get_aws_profile(self) -> str:
        return self._original_profile or os.environ.get("AWS_PROFILE", "")

    def _unset_aws_profile(self):
        if "AWS_PROFILE" in os.environ:
            self._original_profile = os.environ["AWS_PROFILE"]
            os.environ["DOGSTAC_AWS_PROFILE"] = self._original_profile
            del os.environ["AWS_PROFILE"]
            logger.debug(f"Unset AWS_PROFILE from env (stored: {self._original_profile})")

    def get_sso_config(self) -> Optional[SSOConfig]:
        aws_profile = self.get_aws_profile()
        if not aws_profile:
            logger.debug("No AWS_PROFILE set, SSO config unavailable")
            return None

        if not AWS_CONFIG_PATH.exists():
            logger.debug(f"AWS config file not found at {AWS_CONFIG_PATH}")
            return None

        config = configparser.ConfigParser()
        config.read(str(AWS_CONFIG_PATH))

        section = f"profile {aws_profile}"
        if section not in config:
            logger.debug(f"Profile section '{section}' not found in AWS config")
            return None

        profile = config[section]

        sso_session_name = profile.get("sso_session")
        if sso_session_name:
            sso_section = f"sso-session {sso_session_name}"
            if sso_section in config:
                sso_session = config[sso_section]
                start_url = sso_session.get("sso_start_url", profile.get("sso_start_url", ""))
                sso_region = sso_session.get("sso_region", profile.get("sso_region", ""))
            else:
                start_url = profile.get("sso_start_url", "")
                sso_region = profile.get("sso_region", "")
        else:
            start_url = profile.get("sso_start_url", "")
            sso_region = profile.get("sso_region", "")

        account_id = profile.get("sso_account_id", "")
        role_name = profile.get("sso_role_name", "")

        if not all([start_url, sso_region, account_id, role_name]):
            logger.debug(f"Incomplete SSO config for profile '{aws_profile}': "
                         f"start_url={bool(start_url)}, region={bool(sso_region)}, "
                         f"account={bool(account_id)}, role={bool(role_name)}")
            return None

        logger.debug(f"SSO config loaded for profile '{aws_profile}': "
                     f"start_url={start_url}, region={sso_region}, account={account_id}, "
                     f"role={role_name}, session={sso_session_name or '(none)'}")
        return SSOConfig(start_url=start_url, sso_region=sso_region,
                         account_id=account_id, role_name=role_name,
                         session_name=sso_session_name or "")

    def _get_sso_cache_key(self, sso_config: "SSOConfig") -> str:
        if sso_config.session_name:
            return hashlib.sha1(sso_config.session_name.encode("utf-8")).hexdigest()
        return hashlib.sha1(sso_config.start_url.encode("utf-8")).hexdigest()

    def _get_sso_cache_path(self, sso_config: "SSOConfig") -> Path:
        return AWS_SSO_CACHE_DIR / f"{self._get_sso_cache_key(sso_config)}.json"

    def _read_sso_cache(self, sso_config: "SSOConfig") -> Optional[dict]:
        cache_path = self._get_sso_cache_path(sso_config)
        if not cache_path.exists():
            logger.debug(f"SSO cache file not found: {cache_path}")
            return None
        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
            expires_at = data.get("expiresAt", "")
            if expires_at:
                from datetime import datetime, timezone
                normalized = expires_at.replace("UTC", "+00:00").replace("Z", "+00:00")
                expiry = datetime.fromisoformat(normalized)
                if expiry.timestamp() < time.time():
                    logger.debug("SSO cache token expired")
                    return None
            return data
        except Exception as e:
            logger.debug(f"Failed to read SSO cache: {e}")
            return None

    def _write_sso_cache(self, sso_config: "SSOConfig", access_token: str, expires_in: int,
                         refresh_token: str = "", client_id: str = "", client_secret: str = ""):
        AWS_SSO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = self._get_sso_cache_path(sso_config)
        from datetime import datetime, timezone, timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        data = {
            "startUrl": sso_config.start_url,
            "region": sso_config.sso_region,
            "accessToken": access_token,
            "expiresAt": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if refresh_token:
            data["refreshToken"] = refresh_token
        if client_id:
            data["clientId"] = client_id
        if client_secret:
            data["clientSecret"] = client_secret
        with open(cache_path, "w") as f:
            json.dump(data, f)
        logger.debug(f"SSO token cached at {cache_path}, expires at {expires_at}, "
                     f"refresh_token={'present' if refresh_token else 'absent'}")

    def _read_sso_cache_raw(self, sso_config: "SSOConfig") -> Optional[dict]:
        cache_path = self._get_sso_cache_path(sso_config)
        if not cache_path.exists():
            return None
        try:
            with open(cache_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.debug(f"Failed to read raw SSO cache: {e}")
            return None

    def _try_refresh_sso_token(self, sso_config: "SSOConfig") -> bool:
        raw = self._read_sso_cache_raw(sso_config)
        if not raw:
            logger.info("SSO token refresh skipped: no cache file found")
            return False

        refresh_token = raw.get("refreshToken", "")
        client_id = raw.get("clientId", "")
        client_secret = raw.get("clientSecret", "")
        if not all([refresh_token, client_id, client_secret]):
            logger.warning(
                "SSO token refresh impossible: cache missing "
                "refreshToken=%s, clientId=%s, clientSecret=%s",
                bool(refresh_token), bool(client_id), bool(client_secret),
            )
            return False

        try:
            oidc = boto3.client("sso-oidc", region_name=sso_config.sso_region)
            token_response = oidc.create_token(
                clientId=client_id,
                clientSecret=client_secret,
                grantType="refresh_token",
                refreshToken=refresh_token,
            )
            new_access_token = token_response["accessToken"]
            new_expires_in = token_response.get("expiresIn", 28800)
            new_refresh_token = token_response.get("refreshToken", refresh_token)

            self._write_sso_cache(
                sso_config, new_access_token, new_expires_in,
                refresh_token=new_refresh_token,
                client_id=client_id,
                client_secret=client_secret,
            )
            logger.info("SSO access token refreshed via refresh token")
            return True
        except ClientError as e:
            logger.warning(f"SSO token refresh via refresh_token failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error during SSO token refresh: {e}")
            return False

    def try_refresh_credentials(self) -> bool:
        sso_config = self.get_sso_config()
        if not sso_config:
            logger.info("Credential refresh skipped: no SSO config available")
            return False

        cached = self._read_sso_cache(sso_config)
        if not cached:
            logger.info("SSO access token expired or missing, attempting refresh via refresh token")
            if not self._try_refresh_sso_token(sso_config):
                logger.warning("All SSO token refresh methods exhausted, user re-authentication required")
                return False
            cached = self._read_sso_cache(sso_config)
            if not cached:
                return False

        access_token = cached.get("accessToken")
        if not access_token:
            logger.warning("SSO cache present but accessToken field is missing")
            return False

        try:
            sso_client = boto3.client("sso", region_name=sso_config.sso_region)
            creds = sso_client.get_role_credentials(
                roleName=sso_config.role_name,
                accountId=sso_config.account_id,
                accessToken=access_token,
            )
            role_creds = creds["roleCredentials"]
            os.environ["AWS_ACCESS_KEY_ID"] = role_creds["accessKeyId"]
            os.environ["AWS_SECRET_ACCESS_KEY"] = role_creds["secretAccessKey"]
            if role_creds.get("sessionToken"):
                os.environ["AWS_SESSION_TOKEN"] = role_creds["sessionToken"]
            self._unset_aws_profile()
            self._sts_credentials_obtained_at = time.time()
            logger.info("AWS credentials refreshed via SSO token")
            return True
        except ClientError as e:
            logger.warning(f"SSO credential refresh failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error during SSO credential refresh: {e}")
            return False

    def start_sso_login(self) -> Optional[SSOSession]:
        sso_config = self.get_sso_config()
        if not sso_config:
            logger.warning("Cannot start SSO login: no SSO config")
            return None

        try:
            oidc = boto3.client("sso-oidc", region_name=sso_config.sso_region)

            client_reg = oidc.register_client(
                clientName="DogSTAC",
                clientType="public",
                scopes=["sso:account:access"],
                grantTypes=[
                    "urn:ietf:params:oauth:grant-type:device_code",
                    "refresh_token",
                ],
            )
            client_id = client_reg["clientId"]
            client_secret = client_reg["clientSecret"]

            device_auth = oidc.start_device_authorization(
                clientId=client_id,
                clientSecret=client_secret,
                startUrl=sso_config.start_url,
            )

            session_id = str(uuid.uuid4())
            session = SSOSession(
                session_id=session_id,
                client_id=client_id,
                client_secret=client_secret,
                device_code=device_auth["deviceCode"],
                verification_uri=device_auth.get("verificationUriComplete", device_auth["verificationUri"]),
                user_code=device_auth["userCode"],
                expires_at=time.time() + device_auth.get("expiresIn", 600),
                interval=device_auth.get("interval", 5),
                sso_region=sso_config.sso_region,
                start_url=sso_config.start_url,
                account_id=sso_config.account_id,
                role_name=sso_config.role_name,
            )
            self._sso_sessions[session_id] = session
            logger.info(f"SSO device auth started, session_id={session_id}, "
                        f"verification_uri={session.verification_uri}")
            return session
        except Exception as e:
            logger.error(f"Failed to start SSO device authorization: {e}")
            return None

    def poll_sso_token(self, session_id: str) -> dict:
        session = self._sso_sessions.get(session_id)
        if not session:
            return {"status": "expired", "message": "Session not found"}

        if time.time() > session.expires_at:
            session.status = "expired"
            self._sso_sessions.pop(session_id, None)
            return {"status": "expired", "message": "Device authorization expired"}

        if session.status == "complete":
            return {"status": "complete"}

        oidc = boto3.client("sso-oidc", region_name=session.sso_region)
        try:
            token_response = oidc.create_token(
                clientId=session.client_id,
                clientSecret=session.client_secret,
                grantType="urn:ietf:params:oauth:grant-type:device_code",
                deviceCode=session.device_code,
            )

            access_token = token_response["accessToken"]
            expires_in = token_response.get("expiresIn", 28800)
            refresh_token = token_response.get("refreshToken", "")

            logger.info(
                "SSO token obtained: expires_in=%ds, refreshToken=%s",
                expires_in, "present" if refresh_token else "ABSENT",
            )
            if not refresh_token:
                logger.warning(
                    "AWS did not return a refresh token. "
                    "Auto-refresh will NOT work after the access token expires in %ds. "
                    "Check IAM Identity Center session settings.", expires_in,
                )

            sso_config = self.get_sso_config()
            if sso_config:
                self._write_sso_cache(
                    sso_config, access_token, expires_in,
                    refresh_token=refresh_token,
                    client_id=session.client_id,
                    client_secret=session.client_secret,
                )

            try:
                sso_client = boto3.client("sso", region_name=session.sso_region)
                creds = sso_client.get_role_credentials(
                    roleName=session.role_name,
                    accountId=session.account_id,
                    accessToken=access_token,
                )
                role_creds = creds["roleCredentials"]
                os.environ["AWS_ACCESS_KEY_ID"] = role_creds["accessKeyId"]
                os.environ["AWS_SECRET_ACCESS_KEY"] = role_creds["secretAccessKey"]
                if role_creds.get("sessionToken"):
                    os.environ["AWS_SESSION_TOKEN"] = role_creds["sessionToken"]
                self._unset_aws_profile()
                self._sts_credentials_obtained_at = time.time()
                logger.info("SSO login complete, credentials updated")
            except Exception as e:
                logger.warning(f"SSO token obtained but failed to get role credentials: {e}")

            session.status = "complete"
            self._sso_sessions.pop(session_id, None)
            return {"status": "complete"}

        except oidc.exceptions.AuthorizationPendingException:
            return {"status": "pending", "message": "Waiting for user authorization"}
        except oidc.exceptions.SlowDownException:
            return {"status": "pending", "message": "Polling too fast, slowing down"}
        except oidc.exceptions.ExpiredTokenException:
            session.status = "expired"
            self._sso_sessions.pop(session_id, None)
            return {"status": "expired", "message": "Device code expired"}
        except Exception as e:
            logger.error(f"SSO token poll error: {e}")
            return {"status": "error", "message": str(e)}

    def _get_sts_age(self) -> Optional[float]:
        if self._sts_credentials_obtained_at <= 0:
            return None
        return time.time() - self._sts_credentials_obtained_at

    def _is_sts_expiring_soon(self) -> bool:
        age = self._get_sts_age()
        if age is None:
            return False
        return age > (STS_CREDENTIAL_LIFETIME - CREDENTIAL_EXPIRY_BUFFER)

    def get_sso_cache_diagnostics(self) -> dict:
        sso_config = self.get_sso_config()
        if not sso_config:
            return {"available": False, "reason": "no_sso_config"}

        cache_path = self._get_sso_cache_path(sso_config)
        if not cache_path.exists():
            return {"available": False, "reason": "cache_file_missing", "path": str(cache_path)}

        raw = self._read_sso_cache_raw(sso_config)
        if not raw:
            return {"available": False, "reason": "cache_read_error", "path": str(cache_path)}

        has_refresh = bool(raw.get("refreshToken"))
        has_client_id = bool(raw.get("clientId"))
        has_client_secret = bool(raw.get("clientSecret"))
        expires_at = raw.get("expiresAt", "")

        result = {
            "available": True,
            "has_refresh_token": has_refresh,
            "has_client_id": has_client_id,
            "has_client_secret": has_client_secret,
            "expires_at": expires_at,
            "refresh_capable": all([has_refresh, has_client_id, has_client_secret]),
        }

        if expires_at:
            try:
                from datetime import datetime, timezone
                normalized = expires_at.replace("UTC", "+00:00").replace("Z", "+00:00")
                expiry = datetime.fromisoformat(normalized)
                remaining = expiry.timestamp() - time.time()
                result["sso_token_remaining_seconds"] = int(remaining)
                result["sso_token_expired"] = remaining <= 0
            except Exception:
                pass

        sts_age = self._get_sts_age()
        if sts_age is not None:
            result["sts_age_seconds"] = int(sts_age)
            result["sts_remaining_seconds"] = max(0, int(STS_CREDENTIAL_LIFETIME - sts_age))

        return result

    def get_credential_health(self) -> dict:
        aws_profile = self.get_aws_profile()
        sso_config = self.get_sso_config()
        sso_configured = sso_config is not None

        if sso_configured and self._is_sts_expiring_soon():
            sts_age = self._get_sts_age()
            logger.info(
                "STS credentials approaching expiry (age=%ds, lifetime=%ds), triggering proactive refresh",
                int(sts_age or 0), STS_CREDENTIAL_LIFETIME,
            )
            return {
                "status": "expiring_soon",
                "sso_configured": sso_configured,
                "sso_profile": aws_profile,
                "sts_age": int(sts_age or 0),
            }

        try:
            region = os.environ.get("AWS_REGION", "ap-northeast-2")
            access_key = os.environ.get("AWS_ACCESS_KEY_ID")
            secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
            session_token = os.environ.get("AWS_SESSION_TOKEN")
            if access_key and secret_key:
                sts = boto3.client(
                    "sts", region_name=region,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    aws_session_token=session_token,
                )
            else:
                sts = boto3.client("sts", region_name=region)
            identity = sts.get_caller_identity()

            result = {
                "status": "valid",
                "account": identity.get("Account", ""),
                "arn": identity.get("Arn", ""),
                "sso_configured": sso_configured,
                "sso_profile": aws_profile,
            }

            if sso_configured and sso_config:
                cached = self._read_sso_cache(sso_config)
                if cached and cached.get("expiresAt"):
                    from datetime import datetime, timezone
                    expiry = datetime.fromisoformat(
                        cached["expiresAt"].replace("UTC", "+00:00").replace("Z", "+00:00")
                    )
                    remaining = expiry.timestamp() - time.time()
                    result["sso_token_expires_in"] = max(0, int(remaining))
                    if remaining < CREDENTIAL_EXPIRY_BUFFER:
                        result["status"] = "expiring_soon"

            sts_age = self._get_sts_age()
            if sts_age is not None:
                result["sts_age"] = int(sts_age)

            return result

        except Exception as e:
            logger.info(f"Credential health check failed: {e}")
            status = "expired"
            if sso_configured and sso_config:
                raw = self._read_sso_cache_raw(sso_config)
                if raw and raw.get("refreshToken"):
                    status = "refreshable"
            return {
                "status": status,
                "sso_configured": sso_configured,
                "sso_profile": aws_profile,
                "message": str(e),
            }

    def debug_expire_credentials(self, mode: str = "sts") -> dict:
        result = {"mode": mode, "actions": []}

        if mode in ("sts", "all"):
            for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
                if key in os.environ:
                    os.environ[key] = "EXPIRED_DEBUG_VALUE"
            result["actions"].append("sts_credentials_invalidated")
            logger.warning("[DEBUG] STS credentials invalidated")

        if mode in ("sso", "all"):
            sso_config = self.get_sso_config()
            if sso_config:
                cache_path = self._get_sso_cache_path(sso_config)
                if cache_path.exists():
                    cache_path.unlink()
                    result["actions"].append(f"sso_cache_deleted: {cache_path}")
                    logger.warning(f"[DEBUG] SSO cache file deleted at {cache_path}")
                else:
                    result["actions"].append("sso_cache_not_found")
            else:
                result["actions"].append("no_sso_config")

        return result

    async def background_refresh_loop(self):
        logger.info("Credential background refresh loop started")
        while True:
            await asyncio.sleep(CREDENTIAL_HEALTH_INTERVAL)
            try:
                health = await asyncio.to_thread(self.get_credential_health)
                if health["status"] in ("expired", "expiring_soon", "refreshable"):
                    logger.info(
                        "Credential status: %s (sts_age=%s), attempting auto-refresh",
                        health["status"], health.get("sts_age", "unknown"),
                    )
                    refreshed = await asyncio.to_thread(self.try_refresh_credentials)
                    if refreshed:
                        logger.info("Background credential refresh succeeded")
                    else:
                        diag = self.get_sso_cache_diagnostics()
                        logger.warning(
                            "Background credential refresh failed, user action required. "
                            "diagnostics: refresh_capable=%s, sso_token_expired=%s",
                            diag.get("refresh_capable"), diag.get("sso_token_expired"),
                        )
                else:
                    logger.debug(f"Credential health OK: {health['status']}")
            except Exception as e:
                logger.warning(f"Background credential refresh loop error: {e}")


credential_manager = CredentialManager()

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

    def get_sso_config(self) -> Optional[SSOConfig]:
        aws_profile = os.environ.get("AWS_PROFILE", "")
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

    def _write_sso_cache(self, sso_config: "SSOConfig", access_token: str, expires_in: int):
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
        with open(cache_path, "w") as f:
            json.dump(data, f)
        logger.debug(f"SSO token cached at {cache_path}, expires at {expires_at}")

    def try_refresh_credentials(self) -> bool:
        sso_config = self.get_sso_config()
        if not sso_config:
            logger.debug("No SSO config available, cannot refresh")
            return False

        cached = self._read_sso_cache(sso_config)
        if not cached:
            logger.debug("No valid SSO cache token, cannot refresh")
            return False

        access_token = cached.get("accessToken")
        if not access_token:
            logger.debug("SSO cache missing accessToken")
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

            sso_config = self.get_sso_config()
            if sso_config:
                self._write_sso_cache(sso_config, access_token, expires_in)

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

    def get_credential_health(self) -> dict:
        aws_profile = os.environ.get("AWS_PROFILE", "")
        sso_config = self.get_sso_config()
        sso_configured = sso_config is not None

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

            return result

        except Exception as e:
            logger.debug(f"Credential health check failed: {e}")
            return {
                "status": "expired",
                "sso_configured": sso_configured,
                "sso_profile": aws_profile,
                "message": str(e),
            }

    async def background_refresh_loop(self):
        logger.info("Credential background refresh loop started")
        while True:
            await asyncio.sleep(CREDENTIAL_HEALTH_INTERVAL)
            try:
                health = await asyncio.to_thread(self.get_credential_health)
                if health["status"] in ("expired", "expiring_soon"):
                    logger.info(f"Credential status: {health['status']}, attempting auto-refresh")
                    refreshed = await asyncio.to_thread(self.try_refresh_credentials)
                    if refreshed:
                        logger.info("Background credential refresh succeeded")
                    else:
                        logger.warning("Background credential refresh failed, user action required")
                else:
                    logger.debug(f"Credential health OK: {health['status']}")
            except Exception as e:
                logger.warning(f"Background credential refresh loop error: {e}")


credential_manager = CredentialManager()

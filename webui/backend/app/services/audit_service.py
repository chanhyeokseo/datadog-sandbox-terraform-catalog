import asyncio
import json
import logging
import re
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ACTION_MAP: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"/api/terraform/apply/stream/(.+)"), "terraform.apply"),
    (re.compile(r"/api/terraform/plan/stream/(.+)"), "terraform.plan"),
    (re.compile(r"/api/terraform/destroy/stream/(.+)"), "terraform.destroy"),
    (re.compile(r"/api/terraform/init/stream/(.+)"), "terraform.init"),
    (re.compile(r"/api/terraform/init/(.+)/status"), "terraform.init_status"),
    (re.compile(r"/api/terraform/init/(.+)"), "terraform.init"),
    (re.compile(r"/api/terraform/output"), "terraform.output"),
    (re.compile(r"/api/terraform/resources/([^/]+)/variables/(.+)"), "variable.set"),
    (re.compile(r"/api/terraform/resources/([^/]+)/variables"), "variable.list"),
    (re.compile(r"/api/terraform/resources/([^/]+)/description"), "resource.description"),
    (re.compile(r"/api/terraform/resources/([^/]+)/refresh-status"), "resource.refresh_status"),
    (re.compile(r"/api/terraform/resources"), "resource.list"),
    (re.compile(r"/api/terraform/variables/(.+)"), "variable.set_root"),
    (re.compile(r"/api/terraform/variables"), "variable.list_root"),
    (re.compile(r"/api/terraform/security-group/rules"), "security_group.rules"),
    (re.compile(r"/api/terraform/security-group/add-ssh-my-ip"), "security_group.add_ssh_ip"),
    (re.compile(r"/api/terraform/eks/config"), "eks.config"),
    (re.compile(r"/api/terraform/ecs/config"), "ecs.config"),
    (re.compile(r"/api/terraform/docker-agent/config"), "docker_agent.config"),
    (re.compile(r"/api/terraform/credentials/check"), "credentials.check"),
    (re.compile(r"/api/terraform/credentials/sso-login"), "credentials.sso_login"),
    (re.compile(r"/api/terraform/credentials/sso-status/(.+)"), "credentials.sso_status"),
    (re.compile(r"/api/terraform/operations/active"), "operations.active"),
    (re.compile(r"/api/terraform/eks/manage/presets/([^/]+)/deploy"), "eks.deploy"),
    (re.compile(r"/api/terraform/eks/manage/presets/([^/]+)/update"), "eks.update"),
    (re.compile(r"/api/terraform/eks/manage/presets/([^/]+)/undeploy"), "eks.undeploy"),
    (re.compile(r"/api/terraform/eks/manage/presets/([^/]+)/clone"), "eks.clone_preset"),
    (re.compile(r"/api/terraform/eks/manage/presets/([^/]+)/files/(.+)"), "eks.preset_file"),
    (re.compile(r"/api/terraform/eks/manage/presets/([^/]+)"), "eks.preset"),
    (re.compile(r"/api/terraform/eks/manage/presets"), "eks.presets"),
    (re.compile(r"/api/terraform/eks/manage/kubectl"), "eks.kubectl"),
    (re.compile(r"/api/terraform/eks/manage/deployments"), "eks.deployments"),
    (re.compile(r"/api/terraform/ecs/manage/presets/([^/]+)/deploy"), "ecs.deploy"),
    (re.compile(r"/api/terraform/ecs/manage/presets/([^/]+)/undeploy"), "ecs.undeploy"),
    (re.compile(r"/api/terraform/ecs/manage/presets/([^/]+)"), "ecs.preset"),
    (re.compile(r"/api/terraform/ecs/manage/presets"), "ecs.presets"),
    (re.compile(r"/api/terraform/ecs/manage/run"), "ecs.run_command"),
    (re.compile(r"/api/ssh/execute"), "ssh.execute"),
    (re.compile(r"/api/keys/(.+)"), "keys.manage"),
    (re.compile(r"/api/keys"), "keys.list"),
    (re.compile(r"/api/danger-zone/destroy-all/stream"), "danger_zone.destroy_all"),
    (re.compile(r"/api/danger-zone/hard-reset"), "danger_zone.hard_reset"),
]

RESOURCE_PATTERNS: List[Tuple[re.Pattern, int]] = [
    (re.compile(r"/api/terraform/(?:apply|plan|destroy|init)/stream/(.+)"), 1),
    (re.compile(r"/api/terraform/init/(.+?)(?:/status)?$"), 1),
    (re.compile(r"/api/terraform/resources/([^/]+)/"), 1),
    (re.compile(r"/api/terraform/eks/manage/presets/([^/]+)"), 1),
    (re.compile(r"/api/terraform/ecs/manage/presets/([^/]+)"), 1),
]

MUTATING_ACTIONS = {
    "terraform.apply", "terraform.destroy", "terraform.init",
    "variable.set", "variable.set_root",
    "security_group.rules", "security_group.add_ssh_ip",
    "eks.config", "ecs.config", "docker_agent.config",
    "eks.deploy", "eks.update", "eks.undeploy",
    "eks.preset", "eks.clone_preset", "eks.preset_file",
    "ecs.deploy", "ecs.undeploy", "ecs.preset",
    "ecs.run_command", "ssh.execute",
    "danger_zone.destroy_all", "danger_zone.hard_reset",
    "keys.manage",
}


@dataclass
class AuditEntry:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    actor: str = "mcp-client"
    tool_action: str = ""
    resource: str = ""
    status: str = "success"
    duration_ms: int = 0
    method: str = ""
    path: str = ""
    status_code: int = 200

    def to_dict(self) -> dict:
        return asdict(self)


def resolve_action(method: str, path: str) -> str:
    clean = path.rstrip("/")
    for pattern, action in ACTION_MAP:
        if pattern.fullmatch(clean):
            return action
    return f"{method.lower()} {clean}"


def extract_resource(path: str) -> str:
    clean = path.rstrip("/")
    for pattern, group_idx in RESOURCE_PATTERNS:
        m = pattern.search(clean)
        if m:
            return m.group(group_idx)
    return ""


def is_mutating(action: str) -> bool:
    return action in MUTATING_ACTIONS


MAX_ENTRIES = 1000
S3_AUDIT_PREFIX = "audit-logs"


class AuditService:
    def __init__(self):
        self._entries: deque[AuditEntry] = deque(maxlen=MAX_ENTRIES)
        self._s3_manager = None
        self._persist_lock = asyncio.Lock()

    def _get_s3_manager(self):
        if self._s3_manager is not None:
            return self._s3_manager
        try:
            from app.services.config_manager import ConfigManager
            from app.services.s3_config_manager import S3ConfigManager
            cm = ConfigManager()
            name_prefix = cm._get_name_prefix_from_tfvars()
            bucket = cm.generate_bucket_name(name_prefix)
            if bucket:
                self._s3_manager = S3ConfigManager(bucket)
        except Exception as e:
            logger.debug("S3 not available for audit logs: %s", e)
        return self._s3_manager

    def add_entry(self, entry: AuditEntry) -> None:
        self._entries.appendleft(entry)
        logger.debug(
            "Audit: %s %s %s -> %s (%dms)",
            entry.actor, entry.tool_action, entry.resource,
            entry.status, entry.duration_ms,
        )

    async def persist_entry(self, entry: AuditEntry) -> None:
        s3 = self._get_s3_manager()
        if not s3:
            return
        date_str = entry.timestamp[:10]
        s3_key = f"{S3_AUDIT_PREFIX}/{date_str}.jsonl"
        line = json.dumps(entry.to_dict()) + "\n"
        async with self._persist_lock:
            try:
                existing = await asyncio.to_thread(s3.download_text, s3_key)
                updated = existing + line
                await asyncio.to_thread(s3.upload_text, s3_key, updated)
            except Exception as e:
                logger.warning("Failed to persist audit entry to S3: %s", e)

    def get_entries(
        self,
        page: int = 1,
        per_page: int = 25,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict:
        filtered = list(self._entries)
        if status:
            filtered = [e for e in filtered if e.status == status]
        if date_from:
            filtered = [e for e in filtered if e.timestamp >= date_from]
        if date_to:
            filtered = [e for e in filtered if e.timestamp <= date_to + "T23:59:59"]
        total = len(filtered)
        start = (page - 1) * per_page
        page_items = filtered[start : start + per_page]
        return {
            "entries": [e.to_dict() for e in page_items],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
        }

    def get_summary(self) -> Dict:
        entries = list(self._entries)
        total = len(entries)
        successful = sum(1 for e in entries if e.status == "success")
        failed = total - successful
        avg_duration = (
            sum(e.duration_ms for e in entries) / total if total > 0 else 0
        )
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": round(successful / total * 100, 1) if total > 0 else 0,
            "avg_duration_ms": round(avg_duration, 0),
        }

    def load_from_s3(self, days: int = 3) -> None:
        s3 = self._get_s3_manager()
        if not s3:
            logger.debug("S3 not available, skipping audit log load")
            return
        try:
            keys = s3.list_files(S3_AUDIT_PREFIX + "/")
            keys.sort(reverse=True)
            keys = keys[:days]
            loaded = 0
            for key in reversed(keys):
                text = s3.download_text(key)
                if not text:
                    continue
                for line in text.strip().split("\n"):
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entry = AuditEntry(**data)
                        self._entries.append(entry)
                        loaded += 1
                    except Exception:
                        continue
            if loaded:
                logger.info("Loaded %d audit log entries from S3", loaded)
        except Exception as e:
            logger.warning("Failed to load audit logs from S3: %s", e)


audit_service = AuditService()

import json
import logging
import httpx
from mcp.server.fastmcp import FastMCP
from dogstac_client import DogSTACClient

logger = logging.getLogger(__name__)


def register(mcp: FastMCP, client: DogSTACClient):
    async def _check_sg_ssh_rules() -> dict | None:
        try:
            rules = await client.get("/api/terraform/security-group/rules")
            ingress = rules.get("ingress_rules", [])
            ssh_rules = [
                r for r in ingress
                if r.get("from_port") == 22 and r.get("to_port") == 22
            ]
            has_my_ip = any(r.get("use_my_ip") for r in ssh_rules)
            return {
                "ssh_rules_count": len(ssh_rules),
                "has_use_my_ip": has_my_ip,
                "ssh_rules": ssh_rules,
            }
        except Exception as e:
            logger.debug("Failed to check security group rules: %s", e)
            return None

    @mcp.tool()
    async def ssh_execute(hostname: str, command: str, username: str = "ec2-user") -> str:
        """Execute a command on an EC2 instance via SSH and return stdout, stderr, and exit code.
        The SSH key is resolved automatically from the DogSTAC configuration.

        Examples:
        - hostname="54.180.1.100", command="sudo datadog-agent status"
        - hostname="54.180.1.100", command="sudo systemctl restart datadog-agent"
        - hostname="54.180.1.100", command="sudo journalctl -u datadog-agent --no-pager -n 50"
        """
        try:
            result = await client.post(
                "/api/ssh/execute",
                {"hostname": hostname, "command": command, "username": username},
            )
            return json.dumps(result, indent=2)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (502, 504):
                sg_check = await _check_sg_ssh_rules()
                error_detail = e.response.json().get("detail", str(e)) if e.response.headers.get("content-type", "").startswith("application/json") else str(e)
                resp = {
                    "error": error_detail,
                    "hostname": hostname,
                }
                if sg_check and not sg_check["has_use_my_ip"]:
                    resp["diagnosis"] = (
                        "Security group has no SSH rule with your current IP. "
                        "Run add_my_ip_ssh_rule to allow SSH access from your IP, then retry."
                    )
                    resp["sg_ssh_rules"] = sg_check["ssh_rules"]
                elif sg_check and sg_check["has_use_my_ip"]:
                    resp["diagnosis"] = (
                        "Security group SSH rule with use_my_ip exists. "
                        "The issue may be: instance not running, wrong hostname, or network timeout."
                    )
                return json.dumps(resp, indent=2)
            raise

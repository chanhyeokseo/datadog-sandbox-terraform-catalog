import json
from mcp.server.fastmcp import FastMCP
from dogstac_client import DogSTACClient


def register(mcp: FastMCP, client: DogSTACClient):
    @mcp.tool()
    async def get_security_group_rules() -> str:
        """Get current security group ingress and egress rules."""
        data = await client.get("/api/terraform/security-group/rules")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def add_my_ip_ssh_rule() -> str:
        """Allow SSH (port 22) from the current machine's public IP (/32).
        This fetches existing rules, ensures an SSH rule with use_my_ip=true exists,
        saves the rules, and runs terraform apply on the security group.
        """
        rules = await client.get("/api/terraform/security-group/rules")
        ingress = rules.get("ingress_rules", [])
        egress = rules.get("egress_rules", [])

        ssh_exists = any(
            r.get("from_port") == 22 and r.get("to_port") == 22 for r in ingress
        )
        if not ssh_exists:
            ingress.append({
                "description": "Allow SSH from my IP",
                "from_port": 22,
                "to_port": 22,
                "protocol": "tcp",
                "cidr_blocks": [],
                "use_my_ip": True,
            })

        for rule in ingress:
            if rule.get("from_port") == 22 and rule.get("to_port") == 22:
                rule["use_my_ip"] = True

        await client.post(
            "/api/terraform/security-group/rules",
            {"ingress_rules": ingress, "egress_rules": egress},
        )

        result = await client.stream_get(
            "/api/terraform/apply/stream/security_group", auto_approve="true"
        )
        return json.dumps({
            "success": result.get("success", False),
            "exit_code": result.get("exit_code", -1),
            "message": "SSH rule for current IP applied" if result.get("success") else "Failed to apply security group",
            "output": result.get("output", ""),
        }, indent=2)

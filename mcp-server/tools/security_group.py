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
        Ensures an SSH rule with use_my_ip=true exists, saves the rules,
        and runs terraform apply on the security group.
        """
        result = await client.post("/api/terraform/security-group/add-ssh-my-ip")
        return json.dumps(result, indent=2)

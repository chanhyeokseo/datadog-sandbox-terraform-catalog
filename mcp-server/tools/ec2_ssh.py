import json
from mcp.server.fastmcp import FastMCP
from dogstac_client import DogSTACClient


def register(mcp: FastMCP, client: DogSTACClient):
    @mcp.tool()
    async def ssh_execute(hostname: str, command: str, username: str = "ec2-user") -> str:
        """Execute a command on an EC2 instance via SSH and return stdout, stderr, and exit code.
        The SSH key is resolved automatically from the DogSTAC configuration.

        Examples:
        - hostname="54.180.1.100", command="sudo datadog-agent status"
        - hostname="54.180.1.100", command="sudo systemctl restart datadog-agent"
        - hostname="54.180.1.100", command="sudo journalctl -u datadog-agent --no-pager -n 50"
        """
        result = await client.post(
            "/api/ssh/execute",
            {"hostname": hostname, "command": command, "username": username},
        )
        return json.dumps(result, indent=2)

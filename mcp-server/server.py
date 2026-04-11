import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP
from dogstac_client import DogSTACClient
from tools import resource, terraform, security_group, ec2_ssh, eks, ecs, credentials

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)

mcp = FastMCP(
    "DogSTAC",
    instructions=(
        "DogSTAC MCP server provides tools to manage AWS infrastructure "
        "(EC2, EKS, ECS) via Terraform, deploy Datadog agents, execute SSH commands, "
        "and manage security groups. All infrastructure operations go through the "
        "DogSTAC backend API."
    ),
)
client = DogSTACClient()

credentials.register(mcp, client)
resource.register(mcp, client)
terraform.register(mcp, client)
security_group.register(mcp, client)
ec2_ssh.register(mcp, client)
eks.register(mcp, client)
ecs.register(mcp, client)

if __name__ == "__main__":
    mcp.run(transport="stdio")

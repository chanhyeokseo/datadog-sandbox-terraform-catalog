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

MCP_TRANSPORT = os.environ.get("MCP_TRANSPORT", "stdio")
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "7622"))

mcp = FastMCP(
    "DogSTAC",
    host=MCP_HOST,
    port=MCP_PORT,
    instructions=(
        "DogSTAC MCP server provides tools to manage AWS infrastructure "
        "(EC2, EKS, ECS) via Terraform, deploy Datadog agents, execute SSH commands, "
        "and manage security groups. All infrastructure operations go through the "
        "DogSTAC backend API. "
        "For EKS, prefer a declarative approach: define Kubernetes resources, including "
        "Secrets and ConfigMaps, in manifest YAML stored in EKS presets rather than "
        "imperative one-off commands such as kubectl create secret. Manage workloads "
        "primarily through the preset lifecycle (create_eks_preset, update_eks_preset_file, "
        "deploy_eks_preset, update_eks_preset deploy_commands) instead of ad-hoc cluster "
        "mutations when avoidable."
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
    mcp.run(transport=MCP_TRANSPORT)

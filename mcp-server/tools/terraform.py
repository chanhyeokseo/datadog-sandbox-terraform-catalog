import json
from mcp.server.fastmcp import FastMCP
from dogstac_client import DogSTACClient


def register(mcp: FastMCP, client: DogSTACClient):
    @mcp.tool()
    async def terraform_plan(resource_id: str) -> str:
        """Run terraform plan on a resource and return the planned changes."""
        result = await client.stream_get(f"/api/terraform/plan/stream/{resource_id}")
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def terraform_apply(resource_id: str) -> str:
        """Run terraform apply (auto-approve) on a resource. May take up to 20+ minutes for EKS clusters."""
        result = await client.stream_get(
            f"/api/terraform/apply/stream/{resource_id}", auto_approve="true"
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def terraform_destroy(resource_id: str) -> str:
        """Run terraform destroy (auto-approve) on a resource."""
        result = await client.stream_get(
            f"/api/terraform/destroy/stream/{resource_id}", auto_approve="true"
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def terraform_output(resource_id: str) -> str:
        """Get terraform outputs for a deployed resource (e.g. public_ip, instance_id, ssh_command)."""
        data = await client.get("/api/terraform/output", resource_id=resource_id)
        if data.get("success") and data.get("output"):
            try:
                outputs = json.loads(data["output"])
                simplified = {k: v.get("value", v) for k, v in outputs.items()}
                return json.dumps({"success": True, "outputs": simplified}, indent=2)
            except (json.JSONDecodeError, AttributeError):
                pass
        return json.dumps(data, indent=2)

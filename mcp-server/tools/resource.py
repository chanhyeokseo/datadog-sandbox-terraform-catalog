import json
from mcp.server.fastmcp import FastMCP
from dogstac_client import DogSTACClient


def register(mcp: FastMCP, client: DogSTACClient):
    @mcp.tool()
    async def list_resources() -> str:
        """List all available Terraform resources with their deployment status (enabled/disabled)."""
        data = await client.get("/api/terraform/resources")
        resources = data if isinstance(data, list) else data.get("resources", data)
        summary = []
        for r in resources:
            summary.append({
                "id": r.get("id"),
                "name": r.get("name"),
                "type": r.get("type"),
                "status": r.get("status"),
                "description": r.get("description"),
            })
        return json.dumps(summary, indent=2)

    @mcp.tool()
    async def get_resource_details(resource_id: str) -> str:
        """Get detailed info about a resource including its configurable variables and current values."""
        variables = await client.get(f"/api/terraform/resources/{resource_id}/variables")
        try:
            desc_data = await client.get(f"/api/terraform/resources/{resource_id}/description")
            description = desc_data.get("content", "")
        except Exception:
            description = ""
        return json.dumps({
            "resource_id": resource_id,
            "description": description,
            "variables": variables if isinstance(variables, list) else variables.get("variables", variables),
        }, indent=2)

    @mcp.tool()
    async def get_common_variables() -> str:
        """Get root-level common Terraform variables (VPC, region, name_prefix, etc.)."""
        data = await client.get("/api/terraform/variables")
        return json.dumps(data if isinstance(data, list) else data.get("variables", data), indent=2)

    @mcp.tool()
    async def set_variable(variable_name: str, value: str, resource_id: str = "") -> str:
        """Set a Terraform variable. If resource_id is provided, sets it for that resource only; otherwise sets the root-level variable.

        Guardrails enforced by the backend for MCP requests:
        - ec2_instance_type: only t3.micro or t3.medium allowed
        - node_desired_size, node_max_size, ec2_desired_capacity, ec2_max_size: max 3
        """
        body = {"value": value}
        if resource_id:
            result = await client.put(f"/api/terraform/resources/{resource_id}/variables/{variable_name}", body)
        else:
            result = await client.put(f"/api/terraform/variables/{variable_name}", body)
        return json.dumps(result, indent=2)

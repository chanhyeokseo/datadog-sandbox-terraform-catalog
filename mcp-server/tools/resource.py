import json
from mcp.server.fastmcp import FastMCP
from dogstac_client import DogSTACClient


def register(mcp: FastMCP, client: DogSTACClient):
    @mcp.tool()
    async def get_resource_info(resource_id: str = "") -> str:
        """Get Terraform resource information.

        - No resource_id: List all resources with deployment status.
        - With resource_id: Get detailed info including configurable variables and current values.
        """
        if not resource_id:
            data = await client.get("/api/terraform/resources")
            resources = data if isinstance(data, list) else data.get("resources", data)
            summary = [
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "type": r.get("type"),
                    "status": r.get("status"),
                    "description": r.get("description"),
                }
                for r in resources
            ]
            return json.dumps(summary, indent=2)

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
        - Read-only (cannot be changed via MCP): name_prefix, creator, team, region,
          vpc_id, public_subnet_id, public_subnet2_id, private_subnet_id,
          ec2_key_name, datadog_api_key, aws_access_key_id, aws_secret_access_key.
          These are set during onboarding and must be changed via the DogSTAC Web UI.
        """
        body = {"value": value}
        if resource_id:
            result = await client.put(f"/api/terraform/resources/{resource_id}/variables/{variable_name}", body)
        else:
            result = await client.put(f"/api/terraform/variables/{variable_name}", body)
        return json.dumps(result, indent=2)

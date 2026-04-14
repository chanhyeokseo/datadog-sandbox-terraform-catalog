import json
from mcp.server.fastmcp import FastMCP
from dogstac_client import DogSTACClient

VALID_ACTIONS = ("plan", "apply", "destroy", "output")


def register(mcp: FastMCP, client: DogSTACClient):
    @mcp.tool()
    async def terraform(action: str, resource_id: str) -> str:
        """Run a Terraform action on a resource.

        Args:
            action: One of "plan", "apply", "destroy", "output".
                - plan: Preview planned changes.
                - apply: Apply changes (auto-approve). May take 20+ min for EKS.
                - destroy: Destroy the resource (auto-approve).
                - output: Get outputs (e.g. public_ip, instance_id, ssh_command).
            resource_id: The Terraform resource to operate on.
        """
        if action not in VALID_ACTIONS:
            return json.dumps({"error": f"Invalid action '{action}'. Must be one of: {', '.join(VALID_ACTIONS)}"})

        if action == "output":
            data = await client.get("/api/terraform/output", resource_id=resource_id)
            if data.get("success") and data.get("output"):
                try:
                    outputs = json.loads(data["output"])
                    simplified = {k: v.get("value", v) for k, v in outputs.items()}
                    return json.dumps({"success": True, "outputs": simplified}, indent=2)
                except (json.JSONDecodeError, AttributeError):
                    pass
            return json.dumps(data, indent=2)

        kwargs = {}
        if action in ("apply", "destroy"):
            kwargs["auto_approve"] = "true"
        result = await client.stream_get(f"/api/terraform/{action}/stream/{resource_id}", **kwargs)
        return json.dumps(result, indent=2)

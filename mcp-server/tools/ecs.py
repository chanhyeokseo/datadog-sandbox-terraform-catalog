import json
from mcp.server.fastmcp import FastMCP
from dogstac_client import DogSTACClient

PRESET_ACTIONS = ("list", "deploy", "undeploy")
STATUS_TYPES = ("cluster", "workloads", "instances")
STATUS_ENDPOINTS = {
    "cluster": "/api/terraform/ecs/manage/cluster-status",
    "workloads": "/api/terraform/ecs/manage/has-active-workloads",
    "instances": "/api/terraform/ecs/manage/container-instances",
}


def register(mcp: FastMCP, client: DogSTACClient):
    @mcp.tool()
    async def get_ecs_status(info_type: str = "cluster") -> str:
        """Get ECS cluster information.

        Args:
            info_type: One of "cluster", "workloads", "instances".
                - cluster: Cluster status (name, ARN, region).
                - workloads: Active services, running tasks, and deployed presets.
                - instances: EC2 container instances (IDs, IPs, state, type).
        """
        if info_type not in STATUS_TYPES:
            return json.dumps({"error": f"Invalid info_type '{info_type}'. Must be one of: {', '.join(STATUS_TYPES)}"})

        data = await client.get(STATUS_ENDPOINTS[info_type])
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def manage_ecs_preset(action: str, preset_name: str = "") -> str:
        """Manage ECS presets.

        Args:
            action: One of "list", "deploy", "undeploy".
                - list: List available presets (Datadog Agent, nginx, redis, etc.).
                - deploy: Deploy a preset (registers task definitions and creates services).
                - undeploy: Undeploy a preset (scales down, deletes service, deregisters tasks).
            preset_name: Required for deploy/undeploy.
        """
        if action not in PRESET_ACTIONS:
            return json.dumps({"error": f"Invalid action '{action}'. Must be one of: {', '.join(PRESET_ACTIONS)}"})

        if action == "list":
            data = await client.get("/api/terraform/ecs/manage/presets")
            presets = data.get("presets", data) if isinstance(data, dict) else data
            return json.dumps([
                {
                    "name": p.get("name"),
                    "description": p.get("description"),
                    "type": p.get("type"),
                    "built_in": p.get("built_in"),
                }
                for p in presets
            ], indent=2)

        if not preset_name:
            return json.dumps({"error": f"preset_name is required for '{action}'"})

        result = await client.stream_post(f"/api/terraform/ecs/manage/presets/{preset_name}/{action}")
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def run_ecs_command(command: str) -> str:
        """Run an ECS query command (read-only). The command is executed via boto3, not CLI.

        Allowed actions: list-services, list-tasks, describe-clusters, describe-services,
        describe-tasks, list-task-definitions, list-container-instances,
        describe-container-instances, describe-task-definition, list-clusters.

        Examples: "aws ecs list-services", "aws ecs describe-services --services my-svc"
        """
        result = await client.stream_post(
            "/api/terraform/ecs/manage/run",
            {"command": command},
        )
        return result.get("output", json.dumps(result, indent=2))

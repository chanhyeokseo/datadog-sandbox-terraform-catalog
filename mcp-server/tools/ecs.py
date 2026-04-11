import json
from mcp.server.fastmcp import FastMCP
from dogstac_client import DogSTACClient


def register(mcp: FastMCP, client: DogSTACClient):
    @mcp.tool()
    async def list_ecs_presets() -> str:
        """List available ECS presets (Datadog Agent, nginx, redis, etc.)."""
        data = await client.get("/api/terraform/ecs/manage/presets")
        presets = data.get("presets", data) if isinstance(data, dict) else data
        summary = [
            {
                "name": p.get("name"),
                "description": p.get("description"),
                "type": p.get("type"),
                "built_in": p.get("built_in"),
            }
            for p in presets
        ]
        return json.dumps(summary, indent=2)

    @mcp.tool()
    async def deploy_ecs_preset(preset_name: str) -> str:
        """Deploy an ECS preset to the cluster (uses boto3 to register task definitions and create services)."""
        result = await client.stream_post(f"/api/terraform/ecs/manage/presets/{preset_name}/deploy")
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def undeploy_ecs_preset(preset_name: str) -> str:
        """Undeploy an ECS preset from the cluster (scales down, deletes service, deregisters task definitions)."""
        result = await client.stream_post(f"/api/terraform/ecs/manage/presets/{preset_name}/undeploy")
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def get_ecs_cluster_status() -> str:
        """Get ECS cluster status (name, ARN, region)."""
        data = await client.get("/api/terraform/ecs/manage/cluster-status")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def get_ecs_active_workloads() -> str:
        """Get active ECS workloads including services, running tasks, and deployed presets."""
        data = await client.get("/api/terraform/ecs/manage/has-active-workloads")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def get_ecs_container_instances() -> str:
        """Get EC2 container instances in the ECS cluster (instance IDs, IPs, state, type)."""
        data = await client.get("/api/terraform/ecs/manage/container-instances")
        return json.dumps(data, indent=2)

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

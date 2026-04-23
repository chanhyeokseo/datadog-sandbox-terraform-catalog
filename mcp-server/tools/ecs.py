import json
from mcp.server.fastmcp import FastMCP
from dogstac_client import DogSTACClient

DEPLOYMENT_ACTIONS = ("list", "deploy", "update", "undeploy")
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
    async def get_ecs_preset_info(preset_name: str = "", filename: str = "") -> str:
        """Get ECS preset information.

        - No args: List all available presets (Datadog Agent, nginx, redis, etc.).
        - preset_name only: Get preset details including files list and manifest.
        - preset_name + filename: Get the content of a specific file (e.g. task-definition.json).
        """
        if not preset_name:
            data = await client.get("/api/terraform/ecs/manage/presets")
            presets = data.get("presets", data) if isinstance(data, dict) else data
            return json.dumps([
                {
                    "name": p.get("name"),
                    "description": p.get("description"),
                    "type": p.get("type"),
                    "built_in": p.get("built_in"),
                    "files": p.get("files", []),
                }
                for p in presets
            ], indent=2)

        if filename:
            data = await client.get(f"/api/terraform/ecs/manage/presets/{preset_name}/files/{filename}")
            return json.dumps(data, indent=2)

        data = await client.get(f"/api/terraform/ecs/manage/presets/{preset_name}")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def manage_ecs_deployment(action: str, preset_name: str = "") -> str:
        """Manage ECS preset deployments.

        Args:
            action: One of "list", "deploy", "update", "undeploy".
                - list: Get currently deployed presets with deployed_at timestamps.
                - deploy: Deploy a preset (registers task definition and creates service).
                - update: Update a deployed preset (registers new task def revision, updates service).
                - undeploy: Undeploy a preset (scales down, deletes service, deregisters tasks).
            preset_name: Required for deploy/update/undeploy.
        """
        if action not in DEPLOYMENT_ACTIONS:
            return json.dumps({"error": f"Invalid action '{action}'. Must be one of: {', '.join(DEPLOYMENT_ACTIONS)}"})

        if action == "list":
            data = await client.get("/api/terraform/ecs/manage/deployments")
            return json.dumps(data, indent=2)

        if not preset_name:
            return json.dumps({"error": f"preset_name is required for '{action}'"})

        result = await client.stream_post(f"/api/terraform/ecs/manage/presets/{preset_name}/{action}")
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def create_ecs_preset(
        preset_name: str,
        description: str,
        files: dict[str, str],
    ) -> str:
        """Create a new ECS preset with task-definition.json and optional extra files.

        Workflow: create_ecs_preset -> manage_ecs_deployment(deploy) -> verify with run_ecs_command.
        The task-definition.json file defines the ECS task (containers, volumes, launch type).
        Use __DATADOG_API_KEY__ placeholder in task-definition.json for automatic substitution.

        Args:
            preset_name: Unique name (alphanumeric, hyphens, underscores, dots).
            description: Short description of the preset.
            files: Dict of filename->content. Must include "task-definition.json".
        """
        body = {
            "name": preset_name,
            "description": description,
            "type": "aws-ecs",
            "files": files,
        }
        data = await client.post("/api/terraform/ecs/manage/presets", body)
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def clone_ecs_preset(preset_name: str, target_name: str) -> str:
        """Clone an existing ECS preset (including built-in ones) to a new editable copy.

        Use this to customize built-in presets (e.g. clone datadog-linux to add CWS config).

        Args:
            preset_name: Source preset name to clone from.
            target_name: New preset name for the clone.
        """
        data = await client.post(
            f"/api/terraform/ecs/manage/presets/{preset_name}/clone",
            {"target_name": target_name},
        )
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def update_ecs_preset(
        preset_name: str,
        filename: str = "",
        content: str = "",
        description: str | None = None,
    ) -> str:
        """Update an ECS preset file or manifest (non built-in only).

        Two modes:
        - File mode (filename + content): Create or update a file in the preset.
        - Manifest mode (no filename): Update preset description.

        Args:
            preset_name: The preset to update.
            filename: File to create/update (e.g. "task-definition.json"). Triggers file mode.
            content: Full file content. Required when filename is provided.
            description: New description (manifest mode only).
        """
        if filename:
            data = await client.put(
                f"/api/terraform/ecs/manage/presets/{preset_name}/files/{filename}",
                {"content": content},
            )
            return json.dumps(data, indent=2)

        body = {}
        if description is not None:
            body["description"] = description
        data = await client.put(f"/api/terraform/ecs/manage/presets/{preset_name}", body)
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def delete_ecs_preset(preset_name: str) -> str:
        """Delete an ECS preset (non built-in only). Removes the preset and all its files."""
        data = await client.delete(f"/api/terraform/ecs/manage/presets/{preset_name}")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def run_ecs_command(command: str) -> str:
        """Run an ECS command via boto3.

        Read actions: list-services, list-tasks, describe-clusters, describe-services,
        describe-tasks, list-task-definitions, list-container-instances,
        describe-container-instances, describe-task-definition, list-clusters.

        Write actions: run-task, stop-task, update-service, delete-service,
        deregister-task-definition.

        Examples:
            "aws ecs list-services"
            "aws ecs describe-services --services my-svc"
            "aws ecs run-task --task-definition my-task --launch-type FARGATE"
            "aws ecs stop-task --task arn:aws:ecs:...:task/abc123"
        """
        result = await client.stream_post(
            "/api/terraform/ecs/manage/run",
            {"command": command},
        )
        return result.get("output", json.dumps(result, indent=2))

    @mcp.tool()
    async def query_cloudwatch_logs(
        log_group: str,
        filter_pattern: str = "",
        start_time: str = "",
        end_time: str = "",
        limit: int = 100,
    ) -> str:
        """Query CloudWatch Logs for a log group.

        Use this to investigate ECS task logs (awslogs driver), verify Datadog Agent output,
        or reproduce customer log patterns.

        Args:
            log_group: CloudWatch log group name (e.g. "/ecs/my-cluster-datadog").
            filter_pattern: CloudWatch filter pattern (e.g. '{ $.status = "error" }').
                Leave empty to return all events.
            start_time: ISO 8601 start time (e.g. "2025-01-01T00:00:00Z"). Default: last 1 hour.
            end_time: ISO 8601 end time. Default: now.
            limit: Maximum number of log events to return (default 100, max 1000).
        """
        body = {
            "log_group": log_group,
            "filter_pattern": filter_pattern,
            "limit": min(limit, 1000),
        }
        if start_time:
            body["start_time"] = start_time
        if end_time:
            body["end_time"] = end_time
        data = await client.post("/api/terraform/ecs/manage/cloudwatch-logs", body)
        return json.dumps(data, indent=2)

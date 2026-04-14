import json
from mcp.server.fastmcp import FastMCP
from dogstac_client import DogSTACClient

DEPLOYMENT_ACTIONS = ("list", "deploy", "undeploy")


def register(mcp: FastMCP, client: DogSTACClient):
    @mcp.tool()
    async def get_eks_preset_info(preset_name: str = "", filename: str = "") -> str:
        """Get EKS preset information.

        - No args: List all available presets (Datadog Agent, nginx, redis, etc.).
        - preset_name only: Get preset details including deploy/undeploy commands and files.
        - preset_name + filename: Get the content of a specific file in the preset.
        """
        if not preset_name:
            data = await client.get("/api/terraform/eks/manage/presets")
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

        if filename:
            data = await client.get(f"/api/terraform/eks/manage/presets/{preset_name}/files/{filename}")
            return json.dumps(data, indent=2)

        data = await client.get(f"/api/terraform/eks/manage/presets/{preset_name}")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def manage_eks_deployment(action: str, preset_name: str = "") -> str:
        """Manage EKS preset deployments.

        Args:
            action: One of "list", "deploy", "undeploy".
                - list: Get currently deployed presets (preset_name not required).
                - deploy: Deploy a preset. Prefer this over imperative kubectl apply.
                - undeploy: Remove a deployed preset from the cluster.
            preset_name: Required for deploy/undeploy.
        """
        if action not in DEPLOYMENT_ACTIONS:
            return json.dumps({"error": f"Invalid action '{action}'. Must be one of: {', '.join(DEPLOYMENT_ACTIONS)}"})

        if action == "list":
            data = await client.get("/api/terraform/eks/manage/deployments")
            return json.dumps(data, indent=2)

        if not preset_name:
            return json.dumps({"error": f"preset_name is required for '{action}'"})

        result = await client.stream_post(f"/api/terraform/eks/manage/presets/{preset_name}/{action}")
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def run_kubectl(command: str) -> str:
        """Execute a kubectl or helm command on the EKS cluster (read/debug operations).

        Allowed binaries: kubectl, helm, istioctl, kustomize (alias: k -> kubectl).
        Shell operators (|, &&, ;, etc.) are forbidden.

        IMPORTANT: Do NOT use this tool to deploy workloads (kubectl apply/create) or
        to define cluster state imperatively (e.g. kubectl create secret). Put Secrets and
        other resources in preset manifest files, then use create_eks_preset or
        update_eks_preset and manage_eks_deployment.

        Use this tool for: get, describe, logs, exec, top, rollout status, etc.

        Examples: "kubectl get pods -A", "helm list -A", "kubectl logs deploy/nginx"
        """
        result = await client.stream_post(
            "/api/terraform/eks/manage/kubectl",
            {"command": command},
        )
        return result.get("output", json.dumps(result, indent=2))

    @mcp.tool()
    async def create_eks_preset(
        preset_name: str,
        description: str,
        preset_type: str,
        deploy_commands: list[str],
        undeploy_commands: list[str],
        files: dict[str, str],
        update_commands: list[str] | None = None,
    ) -> str:
        """Create a new EKS preset with manifest and files.

        This is the recommended way to deploy any workload to EKS.
        Workflow: create_eks_preset -> manage_eks_deployment(deploy) -> verify with run_kubectl.
        Define Secrets, ConfigMaps, and workloads declaratively in files (e.g. secret.yaml)
        instead of kubectl create secret or similar imperative commands.

        Args:
            preset_name: Unique name (alphanumeric, hyphens, underscores, dots).
            description: Short description of the preset.
            preset_type: "kubectl" or "helm".
            deploy_commands: Commands to run on deploy (e.g. ["kubectl apply -f deployment.yaml"]).
            undeploy_commands: Commands to run on undeploy.
            files: Dict of filename->content (e.g. {"deployment.yaml": "apiVersion: ..."}).
            update_commands: Optional commands to run on update.
        """
        body = {
            "name": preset_name,
            "description": description,
            "type": preset_type,
            "deploy_commands": deploy_commands,
            "update_commands": update_commands or deploy_commands,
            "undeploy_commands": undeploy_commands,
            "files": files,
        }
        data = await client.post("/api/terraform/eks/manage/presets", body)
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def clone_eks_preset(preset_name: str, target_name: str) -> str:
        """Clone an existing EKS preset (including built-in ones) to a new editable copy.

        Args:
            preset_name: Source preset name to clone from.
            target_name: New preset name for the clone.
        """
        data = await client.post(
            f"/api/terraform/eks/manage/presets/{preset_name}/clone",
            {"target_name": target_name},
        )
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def update_eks_preset(
        preset_name: str,
        filename: str = "",
        content: str = "",
        description: str | None = None,
        preset_type: str | None = None,
        deploy_commands: list[str] | None = None,
        update_commands: list[str] | None = None,
        undeploy_commands: list[str] | None = None,
    ) -> str:
        """Update an EKS preset manifest or file (non built-in only).

        Two modes:
        - File mode (filename + content): Create or update a specific file in the preset.
        - Manifest mode (no filename): Update preset metadata. Only provided fields are changed.

        Args:
            preset_name: The preset to update.
            filename: File to create/update (e.g. "deployment.yaml"). Triggers file mode.
            content: Full file content. Required when filename is provided.
            description: New description (manifest mode only).
            preset_type: New type (manifest mode only).
            deploy_commands: New deploy commands (manifest mode only).
            update_commands: New update commands (manifest mode only).
            undeploy_commands: New undeploy commands (manifest mode only).
        """
        if filename:
            data = await client.put(
                f"/api/terraform/eks/manage/presets/{preset_name}/files/{filename}",
                {"content": content},
            )
            return json.dumps(data, indent=2)

        body = {}
        if description is not None:
            body["description"] = description
        if preset_type is not None:
            body["type"] = preset_type
        if deploy_commands is not None:
            body["deploy_commands"] = deploy_commands
        if update_commands is not None:
            body["update_commands"] = update_commands
        if undeploy_commands is not None:
            body["undeploy_commands"] = undeploy_commands
        data = await client.put(f"/api/terraform/eks/manage/presets/{preset_name}", body)
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def delete_eks_preset(preset_name: str) -> str:
        """Delete an EKS preset (non built-in only). Removes the preset and all its files."""
        data = await client.delete(f"/api/terraform/eks/manage/presets/{preset_name}")
        return json.dumps(data, indent=2)

import json
from mcp.server.fastmcp import FastMCP
from dogstac_client import DogSTACClient


def register(mcp: FastMCP, client: DogSTACClient):
    @mcp.tool()
    async def list_eks_presets() -> str:
        """List available EKS presets (Datadog Agent, nginx, redis, etc.)."""
        data = await client.get("/api/terraform/eks/manage/presets")
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
    async def get_eks_preset_details(preset_name: str) -> str:
        """Get detailed info about an EKS preset including deploy/undeploy commands and files."""
        data = await client.get(f"/api/terraform/eks/manage/presets/{preset_name}")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def deploy_eks_preset(preset_name: str) -> str:
        """Deploy an EKS preset to the cluster (e.g. agent-helm, nginx, redis).

        If the preset does not exist, create it first with create_eks_preset.
        """
        result = await client.stream_post(f"/api/terraform/eks/manage/presets/{preset_name}/deploy")
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def undeploy_eks_preset(preset_name: str) -> str:
        """Undeploy an EKS preset from the cluster."""
        result = await client.stream_post(f"/api/terraform/eks/manage/presets/{preset_name}/undeploy")
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def run_kubectl(command: str) -> str:
        """Execute a kubectl or helm command on the EKS cluster (read/debug operations).

        Allowed binaries: kubectl, helm, istioctl, kustomize (alias: k -> kubectl).
        Shell operators (|, &&, ;, etc.) are forbidden.

        IMPORTANT: Do NOT use this tool to deploy workloads (kubectl apply/create).
        Instead, use create_eks_preset to create a reusable preset, then deploy_eks_preset.
        This ensures all deployments are reproducible and manageable via the preset system.

        Use this tool for: get, describe, logs, exec, top, rollout status, etc.

        Examples: "kubectl get pods -A", "helm list -A", "kubectl logs deploy/nginx"
        """
        result = await client.stream_post(
            "/api/terraform/eks/manage/kubectl",
            {"command": command},
        )
        return result.get("output", json.dumps(result, indent=2))

    @mcp.tool()
    async def get_eks_deployments() -> str:
        """Get list of currently deployed EKS presets."""
        data = await client.get("/api/terraform/eks/manage/deployments")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def get_eks_preset_file(preset_name: str, filename: str) -> str:
        """Get the content of a specific file in an EKS preset.

        Examples: get_eks_preset_file("redis", "deployment.yaml")
        """
        data = await client.get(f"/api/terraform/eks/manage/presets/{preset_name}/files/{filename}")
        return json.dumps(data, indent=2)

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
        Workflow: create_eks_preset -> deploy_eks_preset -> verify with run_kubectl.

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
        description: str | None = None,
        preset_type: str | None = None,
        deploy_commands: list[str] | None = None,
        update_commands: list[str] | None = None,
        undeploy_commands: list[str] | None = None,
    ) -> str:
        """Update an EKS preset manifest (non built-in only).

        Only provided fields are updated; omitted fields remain unchanged.
        """
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
    async def update_eks_preset_file(preset_name: str, filename: str, content: str) -> str:
        """Create or update a file in an EKS preset (non built-in only).

        Args:
            preset_name: The preset to update.
            filename: File name (e.g. "deployment.yaml", "values.yaml").
            content: Full file content.
        """
        data = await client.put(
            f"/api/terraform/eks/manage/presets/{preset_name}/files/{filename}",
            {"content": content},
        )
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def delete_eks_preset(preset_name: str) -> str:
        """Delete an EKS preset (non built-in only). Removes the preset and all its files."""
        data = await client.delete(f"/api/terraform/eks/manage/presets/{preset_name}")
        return json.dumps(data, indent=2)

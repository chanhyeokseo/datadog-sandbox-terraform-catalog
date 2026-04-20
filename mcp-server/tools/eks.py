import json
from mcp.server.fastmcp import FastMCP
from dogstac_client import DogSTACClient

DEPLOYMENT_ACTIONS = ("list", "deploy", "undeploy")
SHARE_ACTIONS = ("list_shareable_clusters", "list_approved", "request", "list_incoming", "list_outgoing", "approve", "deny", "delete")


def _shared_params(cluster_name: str | None, owner_prefix: str | None) -> dict | None:
    params = {}
    if cluster_name:
        params["cluster_name"] = cluster_name
    if owner_prefix:
        params["owner_prefix"] = owner_prefix
    return params or None


def register(mcp: FastMCP, client: DogSTACClient):
    @mcp.tool()
    async def manage_cluster_share(
        action: str,
        cluster_name: str = "",
        cluster_arn: str = "",
        owner_prefix: str = "",
        request_id: str = "",
    ) -> str:
        """Manage EKS cluster sharing: request, accept, deny, or remove shares.

        Args:
            action: One of "list_shareable_clusters", "list_approved", "request", "list_incoming", "list_outgoing", "approve", "deny", "delete".
                - list_shareable_clusters: List DogSTAC-managed EKS clusters available for sharing (shows owner_prefix per cluster).
                - list_approved: List clusters already approved for your use. Use returned owner_prefix/cluster_name with other EKS tools.
                - request: Send a share request to a cluster owner. Requires cluster_name, cluster_arn, owner_prefix.
                - list_incoming: List share requests others have sent to you (pending/approved/denied).
                - list_outgoing: List share requests you have sent to others.
                - approve: Approve an incoming share request. Requires request_id.
                - deny: Deny an incoming share request. Requires request_id.
                - delete: Delete/remove a share request (yours or incoming). Requires request_id.
            cluster_name: Target cluster name (required for "request").
            cluster_arn: Target cluster ARN (required for "request").
            owner_prefix: Cluster owner's name_prefix (required for "request").
            request_id: Share request ID (required for "approve", "deny", "delete").
        """
        if action not in SHARE_ACTIONS:
            return json.dumps({"error": f"Invalid action '{action}'. Must be one of: {', '.join(SHARE_ACTIONS)}"})

        if action == "list_shareable_clusters":
            data = await client.get("/api/cluster-share/clusters")
            return json.dumps(data, indent=2)

        if action == "list_approved":
            data = await client.get("/api/cluster-share/shared")
            return json.dumps(data, indent=2)

        if action == "request":
            if not all([cluster_name, cluster_arn, owner_prefix]):
                return json.dumps({"error": "cluster_name, cluster_arn, and owner_prefix are all required for 'request'"})
            data = await client.post("/api/cluster-share/requests", {
                "cluster_name": cluster_name,
                "cluster_arn": cluster_arn,
                "owner_prefix": owner_prefix,
            })
            return json.dumps(data, indent=2)

        if action == "list_incoming":
            data = await client.get("/api/cluster-share/requests/incoming")
            return json.dumps(data, indent=2)

        if action == "list_outgoing":
            data = await client.get("/api/cluster-share/requests/outgoing")
            return json.dumps(data, indent=2)

        if not request_id:
            return json.dumps({"error": f"request_id is required for '{action}'"})

        if action == "approve":
            data = await client.post(f"/api/cluster-share/requests/{request_id}/approve")
            return json.dumps(data, indent=2)

        if action == "deny":
            data = await client.post(f"/api/cluster-share/requests/{request_id}/deny")
            return json.dumps(data, indent=2)

        data = await client.delete(f"/api/cluster-share/requests/{request_id}")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def get_eks_preset_info(preset_name: str = "", filename: str = "",
                                  owner_prefix: str = "") -> str:
        """Get EKS preset information.

        - No args: List all available presets (Datadog Agent, nginx, redis, etc.).
        - preset_name only: Get preset details including deploy/undeploy commands and files.
        - preset_name + filename: Get the content of a specific file in the preset.
        - owner_prefix: When provided, reads presets from the shared cluster owner's repository.
        """
        if owner_prefix:
            if not preset_name:
                data = await client.get("/api/terraform/eks/manage/shared-presets",
                                        owner_prefix=owner_prefix)
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
                data = await client.get(
                    f"/api/terraform/eks/manage/shared-presets/{preset_name}/files/{filename}",
                    owner_prefix=owner_prefix)
                return json.dumps(data, indent=2)
            data = await client.get(f"/api/terraform/eks/manage/shared-presets/{preset_name}",
                                    owner_prefix=owner_prefix)
            return json.dumps(data, indent=2)

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
    async def manage_eks_deployment(action: str, preset_name: str = "",
                                    cluster_name: str = "",
                                    owner_prefix: str = "") -> str:
        """Manage EKS preset deployments.

        Args:
            action: One of "list", "deploy", "undeploy".
                - list: Get currently deployed presets with deployed_at and deployed_by fields.
                - deploy: Deploy a preset. Prefer this over imperative kubectl apply.
                - undeploy: Remove a deployed preset from the cluster.
            preset_name: Required for deploy/undeploy.
            cluster_name: Target shared cluster name. Use with owner_prefix for shared clusters.
            owner_prefix: Owner of the shared cluster. Use with cluster_name for shared clusters.
        """
        if action not in DEPLOYMENT_ACTIONS:
            return json.dumps({"error": f"Invalid action '{action}'. Must be one of: {', '.join(DEPLOYMENT_ACTIONS)}"})

        if action == "list":
            if owner_prefix:
                data = await client.get("/api/terraform/eks/manage/shared-deployments",
                                        owner_prefix=owner_prefix)
            else:
                data = await client.get("/api/terraform/eks/manage/deployments")
            return json.dumps(data, indent=2)

        if not preset_name:
            return json.dumps({"error": f"preset_name is required for '{action}'"})

        result = await client.stream_post(
            f"/api/terraform/eks/manage/presets/{preset_name}/{action}",
            params=_shared_params(cluster_name, owner_prefix),
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def run_kubectl(command: str, cluster_name: str = "") -> str:
        """Execute a kubectl or helm command on the EKS cluster (read/debug operations).

        Allowed binaries: kubectl, helm, istioctl, kustomize (alias: k -> kubectl).
        Shell operators (|, &&, ;, etc.) are forbidden.

        Do NOT use this tool to deploy workloads (kubectl apply/create) or define cluster
        state imperatively. Use create_eks_preset + manage_eks_deployment instead.

        Use this tool for: get, describe, logs, exec, top, rollout status, etc.

        Args:
            command: The kubectl/helm command to execute.
            cluster_name: Target shared cluster name. When provided, runs against the shared cluster
                instead of the user's own cluster.

        Examples: "kubectl get pods -A", "helm list -A", "kubectl logs deploy/nginx"
        """
        body = {"command": command}
        if cluster_name:
            body["cluster_name"] = cluster_name
        result = await client.stream_post(
            "/api/terraform/eks/manage/kubectl",
            body,
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

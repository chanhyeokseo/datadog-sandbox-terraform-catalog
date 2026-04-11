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
        """Deploy an EKS preset to the cluster (e.g. agent-helm, nginx, redis)."""
        result = await client.stream_post(f"/api/terraform/eks/manage/presets/{preset_name}/deploy")
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def undeploy_eks_preset(preset_name: str) -> str:
        """Undeploy an EKS preset from the cluster."""
        result = await client.stream_post(f"/api/terraform/eks/manage/presets/{preset_name}/undeploy")
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def run_kubectl(command: str) -> str:
        """Execute a kubectl or helm command on the EKS cluster.

        Allowed binaries: kubectl, helm, istioctl, kustomize (alias: k -> kubectl).
        Shell operators (|, &&, ;, etc.) are forbidden.

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

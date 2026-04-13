import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.guardrails import (
    GuardrailMiddleware,
    MCP_SOURCE_HEADER,
    MCP_SOURCE_VALUE,
    MCP_READONLY_VARIABLES,
    ALLOWED_INSTANCE_TYPES,
    MAX_NODE_COUNT,
    NODE_COUNT_VARIABLES,
)


@pytest.fixture
def app():
    _app = FastAPI()
    _app.add_middleware(GuardrailMiddleware)

    @_app.post("/api/terraform/security-group/rules")
    async def sg_rules():
        return {"success": True}

    @_app.put("/api/terraform/variables/{var_name}")
    async def root_variable(var_name: str):
        return {"success": True}

    @_app.put("/api/terraform/resources/{resource_id}/variables/{var_name}")
    async def resource_variable(resource_id: str, var_name: str):
        return {"success": True}

    @_app.get("/api/terraform/security-group/rules")
    async def get_sg_rules():
        return {"ingress_rules": [], "egress_rules": []}

    @_app.get("/api/terraform/resources")
    async def list_resources():
        return []

    return _app


@pytest.fixture
def client(app):
    return TestClient(app)


MCP_HEADERS = {MCP_SOURCE_HEADER: MCP_SOURCE_VALUE}


class TestSecurityGroupGuardrail:

    def test_mcp_post_sg_rules_blocked(self, client):
        resp = client.post(
            "/api/terraform/security-group/rules",
            json={"ingress_rules": [], "egress_rules": []},
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 403
        assert "add_my_ip_ssh_rule" in resp.json()["detail"]

    def test_webui_post_sg_rules_allowed(self, client):
        resp = client.post(
            "/api/terraform/security-group/rules",
            json={"ingress_rules": [], "egress_rules": []},
        )
        assert resp.status_code == 200

    def test_mcp_get_sg_rules_allowed(self, client):
        resp = client.get(
            "/api/terraform/security-group/rules",
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 200


class TestInstanceTypeGuardrail:

    @pytest.mark.parametrize("instance_type", sorted(ALLOWED_INSTANCE_TYPES))
    def test_mcp_allowed_instance_type(self, client, instance_type):
        resp = client.put(
            "/api/terraform/variables/ec2_instance_type",
            json={"value": instance_type},
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 200

    @pytest.mark.parametrize("instance_type", ["t3.large", "m5.xlarge", "c5.2xlarge"])
    def test_mcp_blocked_instance_type(self, client, instance_type):
        resp = client.put(
            "/api/terraform/variables/ec2_instance_type",
            json={"value": instance_type},
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 403
        assert "not allowed" in resp.json()["detail"]

    def test_webui_any_instance_type_allowed(self, client):
        resp = client.put(
            "/api/terraform/variables/ec2_instance_type",
            json={"value": "m5.xlarge"},
        )
        assert resp.status_code == 200

    def test_mcp_resource_level_instance_type_blocked(self, client):
        resp = client.put(
            "/api/terraform/resources/ec2_basic/variables/ec2_instance_type",
            json={"value": "t3.large"},
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 403

    def test_mcp_resource_level_instance_type_allowed(self, client):
        resp = client.put(
            "/api/terraform/resources/ec2_basic/variables/ec2_instance_type",
            json={"value": "t3.micro"},
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 200


class TestNodeCountGuardrail:

    @pytest.mark.parametrize("var_name", sorted(NODE_COUNT_VARIABLES))
    def test_mcp_node_count_at_max_allowed(self, client, var_name):
        resp = client.put(
            f"/api/terraform/variables/{var_name}",
            json={"value": str(MAX_NODE_COUNT)},
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 200

    @pytest.mark.parametrize("var_name", sorted(NODE_COUNT_VARIABLES))
    def test_mcp_node_count_over_max_blocked(self, client, var_name):
        resp = client.put(
            f"/api/terraform/variables/{var_name}",
            json={"value": str(MAX_NODE_COUNT + 1)},
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 403
        assert "exceeds maximum" in resp.json()["detail"]

    def test_webui_node_count_over_max_allowed(self, client):
        resp = client.put(
            "/api/terraform/variables/node_desired_size",
            json={"value": "10"},
        )
        assert resp.status_code == 200

    def test_mcp_resource_level_node_count_blocked(self, client):
        resp = client.put(
            "/api/terraform/resources/eks_cluster/variables/node_max_size",
            json={"value": "5"},
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 403

    def test_mcp_node_count_invalid_integer(self, client):
        resp = client.put(
            "/api/terraform/variables/node_desired_size",
            json={"value": "abc"},
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 403
        assert "Invalid integer" in resp.json()["detail"]


class TestReadonlyVariableGuardrail:

    @pytest.mark.parametrize("var_name", sorted(MCP_READONLY_VARIABLES))
    def test_mcp_readonly_variable_blocked(self, client, var_name):
        resp = client.put(
            f"/api/terraform/variables/{var_name}",
            json={"value": "anything"},
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 403
        assert "read-only" in resp.json()["detail"]

    @pytest.mark.parametrize("var_name", ["name_prefix", "vpc_id", "datadog_api_key"])
    def test_webui_readonly_variable_allowed(self, client, var_name):
        resp = client.put(
            f"/api/terraform/variables/{var_name}",
            json={"value": "anything"},
        )
        assert resp.status_code == 200

    def test_mcp_readonly_resource_level_also_blocked(self, client):
        resp = client.put(
            "/api/terraform/resources/ec2_basic/variables/name_prefix",
            json={"value": "new-prefix"},
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 403


class TestUnrelatedVariablesPassThrough:

    def test_mcp_other_variable_allowed(self, client):
        resp = client.put(
            "/api/terraform/variables/ec2_root_volume_size",
            json={"value": "30"},
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 200

    def test_mcp_unrelated_get_allowed(self, client):
        resp = client.get("/api/terraform/resources", headers=MCP_HEADERS)
        assert resp.status_code == 200

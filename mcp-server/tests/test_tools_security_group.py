import json
import pytest
from mcp.server.fastmcp import FastMCP

from tools.security_group import register


@pytest.fixture
def mcp_with_tools(mock_client):
    mcp = FastMCP("test")
    register(mcp, mock_client)
    return mcp, mock_client


class TestGetSecurityGroupRules:

    async def test_returns_rules(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {
            "ingress_rules": [
                {"description": "SSH", "from_port": 22, "to_port": 22, "protocol": "tcp", "cidr_blocks": ["1.2.3.4/32"]}
            ],
            "egress_rules": [],
        }
        tool = mcp._tool_manager._tools["get_security_group_rules"]
        result = json.loads(await tool.run({}))
        assert len(result["ingress_rules"]) == 1
        assert result["ingress_rules"][0]["from_port"] == 22


class TestAddMyIpSshRule:

    async def test_adds_ssh_rule_when_missing(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"ingress_rules": [], "egress_rules": []}
        client.post.return_value = {"success": True}
        client.stream_get.return_value = {"success": True, "exit_code": 0, "output": "Apply complete!"}

        tool = mcp._tool_manager._tools["add_my_ip_ssh_rule"]
        result = json.loads(await tool.run({}))
        assert result["success"] is True
        assert "applied" in result["message"].lower()

        posted_body = client.post.call_args[0][1]
        ssh_rules = [r for r in posted_body["ingress_rules"] if r["from_port"] == 22]
        assert len(ssh_rules) == 1
        assert ssh_rules[0]["use_my_ip"] is True

    async def test_preserves_existing_rules(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {
            "ingress_rules": [
                {"description": "HTTP", "from_port": 80, "to_port": 80, "protocol": "tcp", "cidr_blocks": ["0.0.0.0/0"]},
                {"description": "SSH", "from_port": 22, "to_port": 22, "protocol": "tcp", "cidr_blocks": [], "use_my_ip": True},
            ],
            "egress_rules": [{"description": "All", "from_port": 0, "to_port": 0, "protocol": "-1", "cidr_blocks": ["0.0.0.0/0"]}],
        }
        client.post.return_value = {"success": True}
        client.stream_get.return_value = {"success": True, "exit_code": 0, "output": "No changes."}

        tool = mcp._tool_manager._tools["add_my_ip_ssh_rule"]
        await tool.run({})

        posted_body = client.post.call_args[0][1]
        assert len(posted_body["ingress_rules"]) == 2
        assert len(posted_body["egress_rules"]) == 1

    async def test_reports_failure_on_apply_error(self, mcp_with_tools):
        mcp, client = mcp_with_tools
        client.get.return_value = {"ingress_rules": [], "egress_rules": []}
        client.post.return_value = {"success": True}
        client.stream_get.return_value = {"success": False, "exit_code": 1, "output": "Error"}

        tool = mcp._tool_manager._tools["add_my_ip_ssh_rule"]
        result = json.loads(await tool.run({}))
        assert result["success"] is False

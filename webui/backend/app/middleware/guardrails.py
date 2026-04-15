import json
import re
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

MCP_SOURCE_HEADER = "x-dogstac-source"
MCP_SOURCE_VALUE = "mcp"

ALLOWED_INSTANCE_TYPES = {"t3.micro", "t3.medium"}
MAX_NODE_COUNT = 3
NODE_COUNT_VARIABLES = {
    "node_desired_size",
    "node_max_size",
    "ec2_desired_capacity",
    "ec2_max_size",
}

MCP_READONLY_VARIABLES = {
    "name_prefix",
    "creator",
    "team",
    "region",
    "vpc_id",
    "public_subnet_id",
    "public_subnet2_id",
    "private_subnet_id",
    "ec2_key_name",
    "datadog_api_key",
    "aws_access_key_id",
    "aws_secret_access_key",
}

SG_RULES_PATH = "/api/terraform/security-group/rules"

VARIABLE_PATH_RE = re.compile(
    r"^/api/terraform(?:/resources/[^/]+)?/variables/(?P<var_name>[^/]+)$"
)


def _is_mcp_request(request: Request) -> bool:
    return request.headers.get(MCP_SOURCE_HEADER, "").lower() == MCP_SOURCE_VALUE


class GuardrailMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not _is_mcp_request(request):
            return await call_next(request)

        violation = await self._check_violation(request)
        if violation:
            logger.warning("MCP guardrail violation: %s %s — %s", request.method, request.url.path, violation)
            return JSONResponse(status_code=403, content={"detail": violation})

        return await call_next(request)

    async def _check_violation(self, request: Request) -> str | None:
        path = request.url.path.rstrip("/")

        if request.method == "POST" and path == SG_RULES_PATH:
            return (
                "MCP clients cannot modify security group rules directly. "
                "Use the add_my_ip_ssh_rule tool instead."
            )

        if request.method == "PUT":
            m = VARIABLE_PATH_RE.match(path)
            if m:
                var_name = m.group("var_name")
                return await self._check_variable(request, var_name)

        return None

    async def _check_variable(self, request: Request, var_name: str) -> str | None:
        try:
            body = await request.body()
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, Exception):
            return None

        value = data.get("value")
        if value is None:
            return None

        if var_name in MCP_READONLY_VARIABLES:
            return (
                f"Variable '{var_name}' is read-only for MCP clients. "
                "These variables are configured during onboarding and must not be "
                "changed via MCP. Use the DogSTAC Web UI to modify them if needed."
            )

        if var_name == "ec2_instance_type":
            if str(value) not in ALLOWED_INSTANCE_TYPES:
                return (
                    f"Instance type '{value}' is not allowed via MCP. "
                    f"Allowed types: {sorted(ALLOWED_INSTANCE_TYPES)}"
                )

        if var_name in NODE_COUNT_VARIABLES:
            try:
                count = int(value)
            except (ValueError, TypeError):
                return f"Invalid integer value for {var_name}: {value}"
            if count > MAX_NODE_COUNT:
                return (
                    f"{var_name}={count} exceeds maximum of {MAX_NODE_COUNT} "
                    f"allowed via MCP."
                )

        return None

from __future__ import annotations

import json
import os
from hmac import compare_digest
from pathlib import Path

from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP

from .copilot import DataPlatformCopilot


class StaticTokenVerifier:
    """Verify one deployment secret without logging or persisting it."""

    def __init__(self, expected_token: str, resource: str):
        self.expected_token = expected_token
        self.resource = resource

    async def verify_token(self, token: str) -> AccessToken | None:
        if not compare_digest(token, self.expected_token):
            return None
        return AccessToken(
            token=token,
            client_id="data-platform-operator",
            scopes=["copilot:read"],
            resource=self.resource,
        )


def create_server() -> FastMCP:
    token = os.getenv("MCP_BEARER_TOKEN")
    server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")
    auth = None
    verifier = None
    if token:
        verifier = StaticTokenVerifier(token, server_url)
        auth = AuthSettings(
            issuer_url=server_url,
            resource_server_url=server_url,
            required_scopes=["copilot:read"],
            validate_token_resource=True,
        )
    return FastMCP(
        "data-platform-copilot",
        host=os.getenv("MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("MCP_PORT", "8000")),
        stateless_http=True,
        json_response=True,
        auth=auth,
        token_verifier=verifier,
    )


mcp = create_server()


def knowledge_path() -> Path:
    return Path(os.getenv("KNOWLEDGE_DIR", "knowledge"))


def index_path() -> Path | None:
    configured = os.getenv("RETRIEVAL_INDEX")
    return Path(configured) if configured else None


@mcp.tool()
def ask_platform(question: str) -> str:
    """Answer a data-platform question using approved documents with citations."""
    return DataPlatformCopilot(knowledge_path(), index_path()).ask(question).model_dump_json(indent=2)


@mcp.tool()
def list_approved_sources() -> str:
    """List the approved knowledge sources available to the copilot."""
    sources = sorted(path.name for path in knowledge_path().glob("*.md"))
    return json.dumps({"sources": sources})


@mcp.tool()
def get_pipeline_status(pipeline_name: str) -> str:
    """Return safe synthetic operational status for the portfolio demonstration."""
    allowed = {
        "customer-churn-training": {"status": "healthy", "last_run": "demo", "sla": "daily"},
        "customer-churn-scoring": {"status": "healthy", "last_run": "demo", "sla": "daily"},
    }
    return json.dumps(allowed.get(pipeline_name, {"status": "unknown"}))


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport not in {"stdio", "streamable-http"}:
        raise ValueError("MCP_TRANSPORT must be stdio or streamable-http")
    if transport == "streamable-http" and not os.getenv("MCP_BEARER_TOKEN"):
        raise RuntimeError("MCP_BEARER_TOKEN is required for remote HTTP transport")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()

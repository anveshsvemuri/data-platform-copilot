import json
from asyncio import run

from starlette.testclient import TestClient

from data_platform_copilot.mcp_server import (
    StaticTokenVerifier,
    create_server,
    get_pipeline_status,
    list_approved_sources,
)


def test_status_tool_is_allowlisted():
    assert json.loads(get_pipeline_status("customer-churn-training"))["status"] == "healthy"
    assert json.loads(get_pipeline_status("not-real"))["status"] == "unknown"


def test_sources_tool_lists_knowledge():
    assert "model-card.md" in json.loads(list_approved_sources())["sources"]


def test_static_token_verifier_uses_bearer_scope_and_resource():
    verifier = StaticTokenVerifier("correct-secret", "https://copilot.example.com/mcp")
    accepted = run(verifier.verify_token("correct-secret"))

    assert accepted is not None
    assert accepted.client_id == "data-platform-operator"
    assert accepted.scopes == ["copilot:read"]
    assert accepted.resource == "https://copilot.example.com/mcp"
    assert run(verifier.verify_token("wrong-secret")) is None


def test_remote_transport_rejects_missing_or_invalid_bearer(monkeypatch):
    monkeypatch.setenv("MCP_BEARER_TOKEN", "correct-secret")
    monkeypatch.setenv("MCP_SERVER_URL", "http://localhost/mcp")
    app = create_server().streamable_http_app()

    with TestClient(app, base_url="http://localhost") as client:
        assert client.post("/mcp", json={}).status_code == 401
        assert (
            client.post(
                "/mcp", headers={"Authorization": "Bearer wrong-secret"}, json={}
            ).status_code
            == 401
        )
        accepted = client.post(
            "/mcp", headers={"Authorization": "Bearer correct-secret"}, json={}
        )
        assert accepted.status_code != 401

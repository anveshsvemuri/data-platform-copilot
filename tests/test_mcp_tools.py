import json

from data_platform_copilot.mcp_server import get_pipeline_status, list_approved_sources


def test_status_tool_is_allowlisted():
    assert json.loads(get_pipeline_status("customer-churn-training"))["status"] == "healthy"
    assert json.loads(get_pipeline_status("not-real"))["status"] == "unknown"


def test_sources_tool_lists_knowledge():
    assert "model-card.md" in json.loads(list_approved_sources())["sources"]


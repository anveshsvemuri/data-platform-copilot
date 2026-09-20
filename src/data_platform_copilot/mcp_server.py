from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .copilot import DataPlatformCopilot

mcp = FastMCP("data-platform-copilot")


def knowledge_path() -> Path:
    return Path(os.getenv("KNOWLEDGE_DIR", "knowledge"))


@mcp.tool()
def ask_platform(question: str) -> str:
    """Answer a data-platform question using approved documents with citations."""
    return DataPlatformCopilot(knowledge_path()).ask(question).model_dump_json(indent=2)


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
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()


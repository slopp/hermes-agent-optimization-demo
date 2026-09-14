#!/usr/bin/env python3
"""Validate tool discovery through the checked-out Hermes MCP client.

This uses Hermes' ``register_mcp_servers`` path only. It does not start a model,
send a prompt, or emit a trace.

Run from this demo directory:
  PYTHONPATH=/path/to/hermes-agent:src \
    uv run --with 'mcp==1.28.1' --with 'pyyaml==6.0.3' \
    python scripts/check_hermes_mcp_discovery.py
"""

from __future__ import annotations

import os
from pathlib import Path

from tools.mcp_tool import register_mcp_servers
from model_tools import get_tool_definitions


ROOT = Path(__file__).parents[1]


def main() -> None:
    names = register_mcp_servers(
        {
            "pa_style_enterprise": {
                "command": "python3",
                "args": ["-m", "pa_style_mock_mcp.mcp_stdio"],
                "env": {"PYTHONPATH": str(ROOT / "src"), "PA_STYLE_TOOL_CATALOG": "extended"},
                "connect_timeout": 20,
                "timeout": 60,
            }
        }
    )
    assert len(names) == 15, names
    assert any(name.endswith("__chat_search") for name in names), names
    assert any(name.endswith("__actions_send_message") for name in names), names
    # The run profile explicitly disables Hermes' progressive tool-search
    # bridge, so inspect the raw model-facing catalog here. This proves the
    # selected MCP toolset does not leak built-in Hermes tools.
    restricted = get_tool_definitions(
        enabled_toolsets=["pa_style_enterprise"],
        quiet_mode=True,
        skip_tool_search_assembly=True,
    )
    restricted_names = {tool["function"]["name"] for tool in restricted}
    assert restricted_names == set(names), (restricted_names, names)
    print(f"Hermes MCP discovery and tool isolation passed: tools={len(names)}")


if __name__ == "__main__":
    # Prevent config inherited from a developer machine from affecting this
    # explicit-server smoke test.
    os.environ.pop("HERMES_HOME", None)
    main()

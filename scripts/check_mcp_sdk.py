#!/usr/bin/env python3
"""Run a real MCP SDK client against the local stdio server.

Run with:
    uv run --with 'mcp>=1.0,<2.0' python scripts/check_mcp_sdk.py
"""

from __future__ import annotations

import os
from pathlib import Path

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


ROOT = Path(__file__).parents[1]


async def check() -> None:
    parameters = StdioServerParameters(
        command="python3",
        args=["-m", "pa_style_mock_mcp.mcp_stdio"],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PA_STYLE_TOOL_CATALOG": "extended"},
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            tools = await session.list_tools()
            status = await session.call_tool("connectors.get_status", {"connector": "crm"})
            search = await session.call_tool("chat.search", {"query": "launch blocker"})

    assert initialized.protocolVersion == "2025-03-26", initialized
    assert len(tools.tools) == 15, len(tools.tools)
    assert "needs_auth" in status.content[0].text, status
    assert "chat_launch_blocker" in search.content[0].text, search
    print(f"MCP SDK interoperability passed: protocol={initialized.protocolVersion}, tools={len(tools.tools)}")


if __name__ == "__main__":
    anyio.run(check)

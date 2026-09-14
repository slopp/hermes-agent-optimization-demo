"""Minimal newline-delimited JSON-RPC stdio adapter for the mock tool registry.

The adapter intentionally has no MCP SDK dependency so fixture and tool tests can
run anywhere. Production Hermes wiring may use an MCP SDK adapter over the same
ToolRegistry once its launch configuration is selected.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from .tools import ToolRegistry


def _response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle(request: dict[str, Any], registry: ToolRegistry) -> dict[str, Any] | None:
    """Handle a subset sufficient for tool discovery and calls in a stdio client."""
    method = request.get("method")
    request_id = request.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return _response(request_id, {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}, "serverInfo": {"name": "pa-style-mock-mcp", "version": "0.1.0"}})
    if method == "ping":
        return _response(request_id, {})
    if method == "tools/list":
        return _response(request_id, {"tools": registry.schemas()})
    if method == "tools/call":
        params = request.get("params", {})
        result = registry.call(params.get("name", ""), params.get("arguments", {}))
        return _response(request_id, {"content": [{"type": "text", "text": json.dumps(result)}], "isError": not result.get("ok", False)})
    return _error(request_id, -32601, f"Method not found: {method}")


def main() -> None:
    registry = ToolRegistry()
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = handle(request, registry)
            if response is not None:
                print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            print(json.dumps(_error(None, -32700, "Parse error")), flush=True)


if __name__ == "__main__":
    main()

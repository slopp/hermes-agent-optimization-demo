#!/usr/bin/env python3
"""Verify the built mock-MCP image over its published Streamable HTTP port.

This is intentionally local only: it starts one short-lived container with a
fixture-only token and checks authenticated MCP initialize plus bearer
rejection. It does not publish an image or contact a cloud service.
"""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
from contextlib import closing

import httpx


IMAGE = "pa-style-mock-mcp:local"
TOKEN = "fixture-token-only"


def unused_loopback_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def sse_json(body: str) -> dict[str, object]:
    """Read the one JSON-RPC message in the Streamable HTTP SSE envelope."""
    for line in body.splitlines():
        if line.startswith("data: "):
            value = json.loads(line.removeprefix("data: "))
            if isinstance(value, dict):
                return value
    raise ValueError("MCP response did not contain an SSE data message")


async def main() -> int:
    port = unused_loopback_port()
    name = f"pa-style-container-check-{port}"
    endpoint = f"http://127.0.0.1:{port}/mcp"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "container-check", "version": "1"}},
    }
    subprocess.run(
        ["docker", "run", "--detach", "--rm", "--name", name, "--publish", f"127.0.0.1:{port}:8000", "--env", f"PA_STYLE_MOCK_MCP_TOKEN={TOKEN}", IMAGE],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    try:
        headers = {"Accept": "application/json, text/event-stream", "Authorization": f"Bearer {TOKEN}"}
        async with httpx.AsyncClient(timeout=2) as client:
            response: httpx.Response | None = None
            for _ in range(30):
                try:
                    response = await client.post(endpoint, headers=headers, json=payload)
                    if response.status_code != 503:
                        break
                except httpx.HTTPError:
                    # Docker may have accepted the loopback connection while
                    # uvicorn is still completing its first request.
                    pass
                await asyncio.sleep(0.1)
            if response is None or response.status_code != 200:
                raise RuntimeError(f"authenticated container initialize failed: {None if response is None else response.status_code}")
            message = sse_json(response.text)
            if "result" not in message:
                raise RuntimeError("authenticated container initialize returned no JSON-RPC result")
            session_id = response.headers.get("mcp-session-id")
            if not session_id:
                raise RuntimeError("authenticated container initialize returned no MCP session ID")
            tool_response = await client.post(
                endpoint,
                headers={**headers, "Mcp-Session-Id": session_id},
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "connectors.get_status", "arguments": {"connector": "crm"}},
                },
            )
            if tool_response.status_code != 200 or "needs_auth" not in tool_response.text:
                raise RuntimeError(f"authenticated container tool call failed: {tool_response.status_code}")
            unauthenticated = await client.post(endpoint, headers={"Accept": "application/json, text/event-stream"}, json=payload)
            if unauthenticated.status_code != 401:
                raise RuntimeError(f"unauthenticated container initialize must return 401, got {unauthenticated.status_code}")
    finally:
        subprocess.run(["docker", "rm", "--force", name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Mock MCP container protocol check passed: authenticated_initialize=true, tool_call=true, unauthorized=401")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

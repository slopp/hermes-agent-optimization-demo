#!/usr/bin/env python3
"""Run an authenticated MCP initialize round trip against the local adapter."""

from __future__ import annotations

import asyncio
import os
import socket
import sys
from contextlib import closing
from typing import Any

import httpx


def unused_loopback_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def wait_for_initialize(client: httpx.AsyncClient, url: str, headers: dict[str, str], payload: dict[str, Any]) -> httpx.Response:
    last_error: Exception | None = None
    for _ in range(30):
        try:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 503:
                return response
        except httpx.ConnectError as error:
            last_error = error
        await asyncio.sleep(0.1)
    raise RuntimeError(f"Streamable HTTP adapter did not start: {last_error}")


async def main() -> int:
    port = unused_loopback_port()
    token = "fixture-token-only"
    environment = os.environ.copy()
    environment["PA_STYLE_MOCK_MCP_TOKEN"] = token
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "pa_style_mock_mcp.streamable_http",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--require-bearer-token",
        "--issuer-url",
        "https://mock-mcp.example.test",
        "--resource-server-url",
        "https://mock-mcp.example.test/mcp",
        env=environment,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "fixture-protocol-check", "version": "1"},
        },
    }
    url = f"http://127.0.0.1:{port}/mcp"
    headers = {"Accept": "application/json, text/event-stream"}
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            authenticated = await wait_for_initialize(
                client,
                url,
                {**headers, "Authorization": f"Bearer {token}"},
                payload,
            )
            if authenticated.status_code != 200 or '"result"' not in authenticated.text:
                raise AssertionError(f"authenticated initialize failed: {authenticated.status_code}")
            session_id = authenticated.headers.get("mcp-session-id")
            if not session_id:
                raise AssertionError("authenticated initialize did not establish an MCP session")
            session_headers = {
                **headers,
                "Authorization": f"Bearer {token}",
                "Mcp-Session-Id": session_id,
            }
            list_tools = await client.post(
                url,
                headers=session_headers,
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            )
            if list_tools.status_code != 200 or '"connectors.get_status"' not in list_tools.text:
                raise AssertionError(f"authenticated tools/list failed: {list_tools.status_code}")
            connector_status = await client.post(
                url,
                headers=session_headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "connectors.get_status", "arguments": {"connector": "crm"}},
                },
            )
            if connector_status.status_code != 200 or "needs_auth" not in connector_status.text:
                raise AssertionError(f"authenticated tools/call failed: {connector_status.status_code}")
            unauthorized = await client.post(url, headers=headers, json=payload)
            if unauthorized.status_code != 401:
                raise AssertionError(f"unauthenticated initialize must return 401, got {unauthorized.status_code}")
    finally:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
    print("Streamable HTTP protocol check passed: unauthorized=401, authenticated_initialize=true, tools_list=true, tool_call=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

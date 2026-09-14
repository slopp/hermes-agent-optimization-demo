#!/usr/bin/env python3
"""Verify schema parity and session isolation for the optional HTTP adapter."""

from __future__ import annotations

import asyncio

from pa_style_mock_mcp.streamable_http import SessionRegistries, build_server
from pa_style_mock_mcp.tools import ToolRegistry


class Session:
    pass


async def main() -> int:
    server = build_server(catalog="extended")
    tools = await server.list_tools()
    expected = {schema["name"] for schema in ToolRegistry(catalog="extended").schemas()}
    actual = {tool.name for tool in tools}
    if actual != expected:
        raise AssertionError(f"HTTP adapter tool mismatch: expected={sorted(expected)}, actual={sorted(actual)}")

    authenticated = build_server(catalog="extended", bearer_token="fictional-token")
    verifier = authenticated._token_verifier
    if verifier is None or await verifier.verify_token("fictional-token") is None:
        raise AssertionError("configured bearer token was not accepted")
    if await verifier.verify_token("wrong-token") is not None:
        raise AssertionError("incorrect bearer token was accepted")

    registries = SessionRegistries("extended")
    first, second = Session(), Session()
    first_registry = registries.for_session(first)
    second_registry = registries.for_session(second)
    if first_registry is second_registry:
        raise AssertionError("distinct MCP sessions must not share fixture state")
    draft = first_registry.call("actions.prepare_message", {"channel": "mail", "recipient": "ava.patel@example.test", "body": "fictional"})
    token = draft["approval_token"]
    if not first_registry.call("actions.send_message", {"approval_token": token})["ok"]:
        raise AssertionError("a session must retain its own approval state")
    if second_registry.call("actions.send_message", {"approval_token": token})["error"]["code"] != "APPROVAL_REQUIRED":
        raise AssertionError("approval state leaked across MCP sessions")
    print(f"Streamable HTTP adapter check passed: tools={len(tools)}, session_isolation=true, bearer_auth=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

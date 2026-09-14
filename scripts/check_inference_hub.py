#!/usr/bin/env python3
"""Validate the separate initial-test Inference Hub credential and tool calling.

The script reads INFERENCE_HUB_API_KEY from the process environment only and never
writes it to disk or prints it.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


# This is intentionally not the Build-backed collection route. Keeping a
# distinct variable prevents a Build key from accidentally being sent to the
# Inference Hub endpoint (or vice versa).
DEFAULT_MODEL = "nvidia/nvidia/nemotron-3-ultra"
DEFAULT_ENDPOINT = "https://inference-api.nvidia.com/v1/chat/completions"
HERMES_TOOL_NAME = "mcp__pa_style_enterprise__connectors_get_status"


def request_timeout(value: str | None) -> int:
    """Keep a smoke check bounded rather than leaving a terminal hung."""
    try:
        timeout = int(value or "45")
    except ValueError as error:
        raise ValueError("NVIDIA_INFERENCE_TIMEOUT must be an integer from 1 to 60") from error
    if not 1 <= timeout <= 60:
        raise ValueError("NVIDIA_INFERENCE_TIMEOUT must be an integer from 1 to 60")
    return timeout


def main() -> int:
    api_key = os.environ.get("INFERENCE_HUB_API_KEY")
    if not api_key:
        print("INFERENCE_HUB_API_KEY is not set. Source a local secret file before running this check.")
        return 2
    model = os.environ.get("NVIDIA_INFERENCE_MODEL", DEFAULT_MODEL)
    endpoint = os.environ.get("NVIDIA_INFERENCE_ENDPOINT", DEFAULT_ENDPOINT)
    try:
        timeout = request_timeout(os.environ.get("NVIDIA_INFERENCE_TIMEOUT"))
    except ValueError as error:
        print(error)
        return 2

    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": 256,
        "messages": [
            {"role": "system", "content": "You are a tool-using enterprise agent. Use a tool when the user asks for enterprise facts."},
            {"role": "user", "content": "Check whether the CRM connector is available."},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    # Match Hermes' provider-safe MCP normalization. Inference
                    # Hub rejects dotted function names, while Hermes maps this
                    # name back to connectors.get_status at dispatch time.
                    "name": HERMES_TOOL_NAME,
                    "description": "Check connector availability.",
                    "parameters": {"type": "object", "properties": {"connector": {"type": "string"}}, "required": ["connector"]},
                },
            }
        ],
        "tool_choice": "auto",
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.load(response)
    except urllib.error.HTTPError as error:
        print(f"Inference Hub request failed with HTTP {error.code}. Check the Hub key and model availability.")
        return 1
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        print(f"Inference Hub request failed before a response: {error}. Check endpoint reachability and retry.")
        return 1

    message = body["choices"][0]["message"]
    tool_calls = message.get("tool_calls", [])
    if not tool_calls or tool_calls[0]["function"]["name"] != HERMES_TOOL_NAME:
        print("Inference Hub request succeeded, but the model did not produce the expected tool call.")
        return 1
    print(f"Inference Hub tool-call smoke test passed: model={body.get('model', model)}, tool={HERMES_TOOL_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

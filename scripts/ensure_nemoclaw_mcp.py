#!/usr/bin/env python3
"""Keep the tutorial's quick-tunnel MCP registration usable by NemoClaw."""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import time
from pathlib import Path

TUNNEL_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def tunnel_url(log_text: str) -> str | None:
    """Return the newest quick-tunnel URL in a cloudflared log."""
    matches = TUNNEL_URL.findall(log_text)
    return matches[-1] if matches else None


def healthy_status(output: str, expected_tools: int) -> bool:
    """Recognize the two authoritative success lines from `mcp status`."""
    return (
        "tool discovery: successful" in output and f"tools discovered: {expected_tools}" in output
    )


def _run(command: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=check,
        text=True,
        capture_output=True,
        timeout=120,
    )


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    return True


def _stop_previous_tunnel(pid_file: Path) -> None:
    if not pid_file.exists():
        return
    try:
        pid = int(pid_file.read_text().strip())
    except ValueError:
        return
    if _process_alive(pid):
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            if not _process_alive(pid):
                break
            time.sleep(0.1)


def _start_tunnel(runtime_dir: Path, cloudflared: str, local_url: str) -> str:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    log_path = runtime_dir / "cloudflared.log"
    pid_path = runtime_dir / "cloudflared.pid"
    _stop_previous_tunnel(pid_path)
    with log_path.open("w") as log_file:
        process = subprocess.Popen(
            [cloudflared, "tunnel", "--url", local_url],
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    pid_path.write_text(f"{process.pid}\n")
    for _ in range(30):
        if process.poll() is not None:
            raise RuntimeError(f"cloudflared exited with status {process.returncode}")
        url = tunnel_url(log_path.read_text())
        if url:
            (runtime_dir / "mock-mcp-url").write_text(f"{url}\n")
            return url
        time.sleep(1)
    raise RuntimeError("cloudflared did not publish a quick-tunnel URL within 30 seconds")


def ensure_mcp(
    *,
    sandbox: str,
    name: str,
    runtime_dir: Path,
    local_url: str,
    credential_env: str,
    expected_tools: int,
    cloudflared: str = "cloudflared",
    nemoclaw: str = "nemoclaw",
    openshell: str = "openshell",
) -> str:
    """Return the active URL, repairing a stale quick-tunnel registration."""
    if not os.environ.get(credential_env):
        raise RuntimeError(f"{credential_env} is not set")

    status_command = [nemoclaw, sandbox, "mcp", "status", name, "--tools"]
    status = _run(status_command)
    url_path = runtime_dir / "mock-mcp-url"
    if status.returncode == 0 and healthy_status(status.stdout + status.stderr, expected_tools):
        return url_path.read_text().strip() if url_path.exists() else "registered"

    url = _start_tunnel(runtime_dir, cloudflared, local_url)

    # NemoClaw 0.0.124 does not change an existing MCP URL via `mcp add`.
    # Its forced removal deliberately preserves the backing provider, so remove
    # that sandbox-scoped provider before recreating the registration.
    _run([nemoclaw, sandbox, "mcp", "remove", name, "--force"])
    _run([openshell, "provider", "delete", f"{sandbox}-mcp-{name}"])
    added = _run(
        [
            nemoclaw,
            sandbox,
            "mcp",
            "add",
            name,
            "--url",
            f"{url}/mcp",
            "--env",
            credential_env,
        ]
    )
    if added.returncode != 0:
        detail = (added.stderr or added.stdout).strip()
        raise RuntimeError(f"NemoClaw MCP registration failed: {detail}")

    status = _run(status_command)
    output = status.stdout + status.stderr
    if status.returncode != 0 or not healthy_status(output, expected_tools):
        raise RuntimeError("NemoClaw MCP discovery did not reach the expected tool count")
    return url


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sandbox", default="hermes-demo")
    parser.add_argument("--name", default="enterprise-world")
    parser.add_argument("--runtime-dir", type=Path, default=Path(".runs/runtime"))
    parser.add_argument("--local-url", default="http://127.0.0.1:8000")
    parser.add_argument("--credential-env", default="PA_STYLE_MOCK_MCP_TOKEN")
    parser.add_argument("--expected-tools", type=int, default=15)
    parser.add_argument("--cloudflared", default="cloudflared")
    args = parser.parse_args()

    url = ensure_mcp(
        sandbox=args.sandbox,
        name=args.name,
        runtime_dir=args.runtime_dir,
        local_url=args.local_url,
        credential_env=args.credential_env,
        expected_tools=args.expected_tools,
        cloudflared=args.cloudflared,
    )
    print(f"MCP ready: {args.name} ({args.expected_tools} tools) via {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

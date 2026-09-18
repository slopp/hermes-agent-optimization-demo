#!/usr/bin/env python3
"""Run the enterprise fidelity matrix through a NemoClaw/Hermes sandbox."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

TERMINAL_FAILURE_MARKERS = (
    "api call failed after",
    "context length exceeded",
    "service temporarily overloaded",
)


def terminal_failure(response: str) -> str | None:
    """Return the recorded terminal error marker Hermes may emit with exit 0."""
    lowered = response.lower()
    return next((marker for marker in TERMINAL_FAILURE_MARKERS if marker in lowered), None)


def clear_demo_sessions(gateway: str, sandbox: str) -> None:
    """Clear session history in an explicitly disposable demo sandbox."""
    script = """import sqlite3, subprocess
path = '/sandbox/.hermes/runtime/state.db'
ids = [row[0] for row in sqlite3.connect(path).execute('select id from sessions')]
for session_id in ids:
    subprocess.run(['hermes', 'sessions', 'delete', '--yes', session_id], check=True, stdout=subprocess.DEVNULL)
"""
    subprocess.run(
        [
            "openshell", "-g", gateway, "sandbox", "exec", "-n", sandbox,
            "--no-tty", "--", "python", "-c", script,
        ],
        check=True,
        text=True,
        capture_output=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sandbox", default="hermes-demo")
    parser.add_argument("--gateway", default="nemoclaw-18080")
    parser.add_argument("--matrix", type=Path, default=Path("experiments/fidelity-matrix-v2.json"))
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--scenario", action="append", help="Run only the named scenario; repeatable.")
    parser.add_argument("--arm", choices=["baseline", "candidate"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0,
        help="Pause between runs to avoid bursting a shared inference endpoint.",
    )
    parser.add_argument(
        "--terminal-retries",
        type=int,
        default=0,
        help="Retry a logical trial when Hermes returns a recognized terminal provider error.",
    )
    parser.add_argument(
        "--retry-backoff-seconds",
        type=float,
        default=120,
        help="Cooldown before retrying a terminal provider error.",
    )
    parser.add_argument("--model", help="Optional Hermes model override for every invocation.")
    parser.add_argument("--provider", help="Optional Hermes provider override for every invocation.")
    parser.add_argument(
        "--toolsets",
        help=(
            "Optional comma-separated Hermes built-in/plugin toolsets. MCP tools "
            "remain available through Hermes tool search."
        ),
    )
    parser.add_argument(
        "--reset-demo-sessions",
        action="store_true",
        help="Delete prior Hermes sessions before every run; only use with a disposable demo sandbox.",
    )
    args = parser.parse_args()

    matrix = json.loads(args.matrix.read_text())
    scenarios = matrix["scenarios"]
    if args.scenario:
        requested = set(args.scenario)
        scenarios = [scenario for scenario in scenarios if scenario["id"] in requested]
        missing = requested - {scenario["id"] for scenario in scenarios}
        if missing:
            parser.error(f"unknown scenario(s): {', '.join(sorted(missing))}")
    args.output.mkdir(parents=True, exist_ok=True)
    failures = 0
    for trial in range(1, args.trials + 1):
        for scenario in scenarios:
            case_id = scenario["id"]
            print(f"[{args.arm}] {case_id} trial {trial}/{args.trials}", flush=True)
            logical_trial_failed = False
            for attempt in range(1, args.terminal_retries + 2):
                if args.reset_demo_sessions:
                    clear_demo_sessions(args.gateway, args.sandbox)
                run_workspace = (
                    f"/sandbox/eval-workspaces/{args.arm}-{case_id}-{trial}-"
                    f"{uuid.uuid4().hex[:8]}"
                )
                subprocess.run(
                    [
                        "openshell", "-g", args.gateway, "sandbox", "exec", "-n",
                        args.sandbox, "--no-tty", "--", "mkdir", "-p", run_workspace,
                    ],
                    check=True,
                    text=True,
                    capture_output=True,
                )
                command = [
                    "openshell", "-g", args.gateway, "sandbox", "exec", "-n",
                    args.sandbox, "--timeout", str(args.timeout), "--no-tty", "--",
                    "hermes", "-z", scenario["prompt"], "--in", run_workspace,
                ]
                if args.toolsets:
                    command.extend(["--toolsets", args.toolsets])
                if args.model:
                    command.extend(["--model", args.model])
                if args.provider:
                    command.extend(["--provider", args.provider])
                completed = subprocess.run(
                    command,
                    text=True,
                    capture_output=True,
                    timeout=args.timeout + 30,
                    check=False,
                )
                response = completed.stdout.strip()
                terminal_error = terminal_failure(response)
                record = {
                    "schema_version": "nemoclaw-matrix-run-v1",
                    "arm": args.arm,
                    "case_id": case_id,
                    "trial": trial,
                    "attempt": attempt,
                    "prompt": scenario["prompt"],
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "returncode": completed.returncode,
                    "response": response,
                    "stderr": completed.stderr.strip(),
                    "terminal_error": terminal_error,
                    "workspace": run_workspace,
                }
                path = args.output / f"{case_id}-trial-{trial:02d}.json"
                path.write_text(json.dumps(record, indent=2) + "\n")
                if terminal_error:
                    attempt_path = args.output / (
                        f"{case_id}-trial-{trial:02d}-attempt-{attempt:02d}.json"
                    )
                    attempt_path.write_text(json.dumps(record, indent=2) + "\n")
                if terminal_error and attempt <= args.terminal_retries:
                    print(
                        f"  {terminal_error}; retrying attempt {attempt + 1}/"
                        f"{args.terminal_retries + 1} after {args.retry_backoff_seconds:g}s",
                        flush=True,
                    )
                    time.sleep(args.retry_backoff_seconds)
                    continue
                logical_trial_failed = bool(completed.returncode or terminal_error)
                if logical_trial_failed:
                    detail = completed.stderr.strip() or terminal_error or "unknown failure"
                    print(f"  failed with exit {completed.returncode}: {detail}", flush=True)
                break
            if logical_trial_failed:
                failures += 1
            if args.delay_seconds > 0:
                time.sleep(args.delay_seconds)
    print(f"Completed {len(scenarios) * args.trials} runs; failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

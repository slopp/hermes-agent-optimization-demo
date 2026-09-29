#!/usr/bin/env python3
"""Run one baseline or candidate arm on the development or held-out Harbor set."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("baseline", "candidate"), required=True)
    parser.add_argument("--split", choices=("development", "held-out"), required=True)
    parser.add_argument(
        "--runtime",
        choices=("openshell", "direct"),
        default="openshell",
        help="Run Hermes in OpenShell (default) or directly in the Harbor task image.",
    )
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--harbor", default="harbor")
    parser.add_argument("--jobs-dir", type=Path, default=ROOT / ".runs" / "harbor")
    parser.add_argument("--job-name")
    parser.add_argument(
        "--model", default="nvidia/nvidia/nemotron-3-ultra-550b-a55b"
    )
    parser.add_argument("--openshell-bin", default="openshell")
    parser.add_argument("--openshell-image", default="hermes-flywheel-openshell:0.2")
    parser.add_argument("--openshell-provider", default="hermes-nvidia")
    parser.add_argument("--provider-base-url", default="")
    args = parser.parse_args()
    if args.attempts < 1 or args.concurrency < 1:
        parser.error("--attempts and --concurrency must be positive")

    suite = json.loads((ROOT / "evals" / "flywheel-eval-set-v2.json").read_text())
    case_kind = "held_out" if args.split == "held-out" else "trace_derived"
    case_ids = [case["id"] for case in suite["cases"] if case["case_kind"] == case_kind]
    job_name = args.job_name or f"{args.arm}-{args.split}"
    agent = (
        "harbor_agents.openshell_hermes:OpenShellHermesFlywheel"
        if args.runtime == "openshell"
        else "harbor_agents.hermes_flywheel:HermesFlywheel"
    )
    command = [
        args.harbor,
        "run",
        "-p",
        str(ROOT / "evals" / "harbor-tasks-v2"),
        "-a",
        agent,
        "--ak",
        f"arm={args.arm}",
        "-m",
        args.model,
        "--jobs-dir",
        str(args.jobs_dir),
        "--job-name",
        job_name,
        "--n-attempts",
        str(args.attempts),
        "--n-concurrent",
        str(args.concurrency),
        "--yes",
    ]
    if args.runtime == "openshell":
        command.extend(("--ak", f"openshell_bin={args.openshell_bin}"))
        command.extend(("--ak", f"openshell_image={args.openshell_image}"))
        command.extend(("--ak", f"openshell_provider={args.openshell_provider}"))
        if args.provider_base_url:
            command.extend(("--ak", f"provider_base_url={args.provider_base_url}"))
    for case_id in case_ids:
        command.extend(("--include-task-name", case_id))
    print(
        json.dumps(
            {
                "arm": args.arm,
                "split": args.split,
                "runtime": args.runtime,
                "cases": case_ids,
                "job": job_name,
            }
        )
    )
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{ROOT}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(ROOT)
    )
    return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

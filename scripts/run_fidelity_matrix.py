#!/usr/bin/env python3
"""Run the public fidelity matrix through the real Hermes collection launcher.

The script starts real model runs only. It never creates trace-shaped fixture
data or infers a pass/fail result from the scenario description.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parents[1]
DEFAULT_MATRIX = ROOT / "experiments" / "fidelity-matrix.json"
DEFAULT_BUILD_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"
DEFAULT_HUB_MODEL = "nvidia/nvidia/nemotron-3-ultra"
DEFAULT_HUB_ENDPOINT = "https://inference-api.nvidia.com/v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_collection_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def require_empty_run_root(path: Path) -> None:
    """Do not let a new matrix invocation mix ATIF files with an old one."""
    if path.exists() and any(path.iterdir()):
        raise ValueError(f"collection run root already exists and is not empty: {path}; choose a new --collection-id or --run-root")


def load_matrix(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or not isinstance(value.get("scenarios"), list):
        raise ValueError("matrix must be an object containing scenarios")
    if not value["scenarios"]:
        raise ValueError("matrix must contain at least one scenario")
    for scenario in value["scenarios"]:
        if not isinstance(scenario, dict) or not isinstance(scenario.get("id"), str) or not isinstance(scenario.get("prompt"), str):
            raise ValueError("every matrix scenario requires string id and prompt fields")
    return value


def select_scenarios(matrix: dict[str, Any], requested_ids: set[str] | None) -> list[dict[str, Any]]:
    scenarios = matrix["scenarios"]
    known_ids = {scenario["id"] for scenario in scenarios}
    unknown = sorted((requested_ids or set()) - known_ids)
    if unknown:
        raise ValueError(f"unknown scenario IDs: {', '.join(unknown)}")
    return [scenario for scenario in scenarios if requested_ids is None or scenario["id"] in requested_ids]


def build_jobs(scenarios: list[dict[str, Any]], trials: int, arm: str) -> list[dict[str, Any]]:
    if trials < 1:
        raise ValueError("trials must be at least 1")
    return [
        {
            "scenario_id": scenario["id"],
            "trial": trial,
            "case_id": f"{scenario['id']}-trial-{trial:02d}",
            "prompt": scenario["prompt"],
            "arm": arm,
        }
        for scenario in scenarios
        for trial in range(1, trials + 1)
    ]


def write_manifest(
    path: Path,
    matrix_path: Path,
    arm: str,
    trials: int,
    tool_catalog: str,
    inference_route: str,
    provider: str,
    model: str,
    wall_timeout_seconds: int,
    collection_id: str,
    run_root: Path,
    records: list[dict[str, Any]],
) -> None:
    # Do not include prompts, answers, calls, or Relay content in this index.
    manifest = {
        "schema_version": "fidelity-collection-manifest-v1",
        "generated_at": utc_now(),
        "matrix_path": str(matrix_path),
        "matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
        "arm": arm,
        "tool_catalog": tool_catalog,
        "inference_route": inference_route,
        "provider": provider,
        "model": model,
        "wall_timeout_seconds": wall_timeout_seconds,
        "collection_id": collection_id,
        "run_root": str(run_root),
        "trials_per_scenario": trials,
        "records": records,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--arm", choices=["baseline", "candidate"], default="baseline")
    parser.add_argument("--trials", type=int, help="Override the matrix baseline trial count")
    parser.add_argument("--tool-catalog", choices=["focused", "extended"], help="Override the matrix tool catalog for every run")
    parser.add_argument("--scenario", action="append", help="Scenario ID to run; may be repeated")
    parser.add_argument("--keep-going", action="store_true", help="Continue after a failed Hermes run")
    parser.add_argument("--dry-run", action="store_true", help="Print the collection plan without launching a model")
    parser.add_argument("--manifest", type=Path, help="Ignored local metadata manifest path")
    parser.add_argument("--candidate-experiment", type=Path, help="Required reviewed candidate manifest when --arm candidate")
    parser.add_argument("--trace-derived-suite", type=Path, help="Required frozen suite when --arm candidate")
    parser.add_argument("--inference-route", choices=["build", "hub-test"], default="build")
    parser.add_argument("--hub-endpoint", default=DEFAULT_HUB_ENDPOINT, help="Custom-provider base URL for --inference-route hub-test")
    parser.add_argument("--hub-model", default=DEFAULT_HUB_MODEL, help="Model for --inference-route hub-test")
    parser.add_argument("--run-root", type=Path, help="Ignored local root for this route/arm")
    parser.add_argument("--collection-id", help="Unique ignored subdirectory name; defaults to a UTC timestamp")
    args = parser.parse_args()

    matrix = load_matrix(args.matrix)
    default_trials = matrix.get("go_no_go", {}).get("baseline_trials_per_scenario", 5)
    trials = args.trials if args.trials is not None else default_trials
    if not isinstance(trials, int):
        raise SystemExit("error: trial count must be an integer")
    jobs = build_jobs(select_scenarios(matrix, set(args.scenario) if args.scenario else None), trials, args.arm)
    tool_catalog = args.tool_catalog or matrix.get("collection_defaults", {}).get("tool_catalog", "extended")
    if tool_catalog not in {"focused", "extended"}:
        raise SystemExit("error: matrix collection_defaults.tool_catalog must be focused or extended")

    if args.dry_run:
        print(json.dumps([{key: job[key] for key in ("scenario_id", "trial", "case_id", "arm")} for job in jobs], indent=2))
        return 0

    if args.arm == "candidate":
        if not args.candidate_experiment or not args.trace_derived_suite:
            raise SystemExit("error: --candidate-experiment and --trace-derived-suite are required for candidate collection")
        if not args.candidate_experiment.is_file() or not args.trace_derived_suite.is_file():
            raise SystemExit("error: candidate experiment and trace-derived suite must both exist")

    if not os.environ.get("HERMES_SOURCE"):
        raise SystemExit("error: HERMES_SOURCE must point to a Hermes checkout")
    if args.inference_route == "build":
        if not os.environ.get("NVIDIA_API_KEY"):
            raise SystemExit("error: NVIDIA_API_KEY must be supplied through the environment for the Build route")
        provider = "nvidia"
        model = os.environ.get("HERMES_MODEL", DEFAULT_BUILD_MODEL)
    else:
        if not os.environ.get("INFERENCE_HUB_API_KEY"):
            raise SystemExit("error: INFERENCE_HUB_API_KEY must be supplied through the environment for the Hub test route")
        provider = "custom"
        model = args.hub_model
    try:
        wall_timeout_seconds = int(os.environ.get("HERMES_RUN_TIMEOUT_SECONDS", "180"))
    except ValueError as error:
        raise SystemExit("error: HERMES_RUN_TIMEOUT_SECONDS must be a positive integer") from error
    if wall_timeout_seconds < 1:
        raise SystemExit("error: HERMES_RUN_TIMEOUT_SECONDS must be a positive integer")

    default_root = ROOT / ".runs" / ("hub-test" / Path(args.arm) if args.inference_route == "hub-test" else Path(args.arm))
    collection_id = args.collection_id or default_collection_id()
    if not collection_id or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-" for character in collection_id):
        raise SystemExit("error: --collection-id must contain only letters, numbers, dot, underscore, or hyphen")
    run_root = args.run_root or default_root / collection_id
    try:
        require_empty_run_root(run_root)
    except ValueError as error:
        raise SystemExit(f"error: {error}") from error
    manifest_path = args.manifest or run_root / "fidelity-collection-manifest.json"
    launcher = ROOT / "scripts" / "run_hermes_case.sh"
    records: list[dict[str, Any]] = []
    failed = False
    for job in jobs:
        run_directory = run_root / job["case_id"]
        environment = os.environ.copy()
        environment["RUN_DIRECTORY"] = str(run_directory)
        environment["HERMES_TOOL_CATALOG"] = tool_catalog
        environment["HERMES_PROVIDER"] = provider
        environment["HERMES_MODEL"] = model
        environment["HERMES_COLLECTION_MODE"] = "local-hermes"
        environment["HERMES_INFERENCE_ROUTE"] = args.inference_route
        if args.inference_route == "hub-test":
            environment["HERMES_BASE_URL"] = args.hub_endpoint
        if args.arm == "candidate":
            environment["HERMES_CANDIDATE_EXPERIMENT"] = str(args.candidate_experiment.resolve())
            environment["HERMES_TRACE_DERIVED_SUITE"] = str(args.trace_derived_suite.resolve())
        started_at = utc_now()
        result = subprocess.run(
            [str(launcher), job["case_id"], job["prompt"], args.arm],
            cwd=ROOT,
            env=environment,
            check=False,
        )
        records.append(
            {
                "scenario_id": job["scenario_id"],
                "trial": job["trial"],
                "case_id": job["case_id"],
                "arm": args.arm,
                "started_at": started_at,
                "exit_code": result.returncode,
                "run_directory": str(run_directory),
                "tool_catalog": tool_catalog,
                "inference_route": args.inference_route,
                "provider": provider,
                "model": model,
                "wall_timeout_seconds": wall_timeout_seconds,
            }
        )
        if result.returncode:
            failed = True
            if not args.keep_going:
                break
    write_manifest(
        manifest_path,
        args.matrix,
        args.arm,
        trials,
        tool_catalog,
        args.inference_route,
        provider,
        model,
        wall_timeout_seconds,
        collection_id,
        run_root,
        records,
    )
    print(f"Wrote local collection manifest: {manifest_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        raise SystemExit(f"error: {error}")

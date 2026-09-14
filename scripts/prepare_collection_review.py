#!/usr/bin/env python3
"""Create a content-safe dossier for reviewing one ignored fidelity collection.

The dossier joins the metadata-only ATIF inventory with the public matrix's
observed tool-signal coverage.  It deliberately excludes scenario prompts,
model answers, tool arguments, tool results, and credentials.  It is useful
for selecting raw artifacts for human review, but is not an approval or an
Insights Intake upload.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parents[1]


def load_script(name: str) -> Any:
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SUMMARY = load_script("summarize_collection")
COVERAGE = load_script("check_fidelity_coverage")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collector_manifest(run_root: Path, arm: str, trials: int) -> dict[str, Any]:
    """Return safe manifest metadata after binding its records to the run root."""
    path = run_root / "fidelity-collection-manifest.json"
    if not path.is_file():
        raise ValueError(f"missing fidelity collection manifest: {path}")
    value = json.loads(path.read_text())
    if not isinstance(value, dict) or value.get("schema_version") != "fidelity-collection-manifest-v1":
        raise ValueError("collector manifest has an unsupported schema")
    if value.get("arm") != arm:
        raise ValueError("collector manifest arm does not match requested dossier arm")
    if value.get("trials_per_scenario") != trials:
        raise ValueError("collector manifest trials_per_scenario does not match --trials")
    records = value.get("records")
    if not isinstance(records, list) or not all(isinstance(record, dict) and isinstance(record.get("case_id"), str) for record in records):
        raise ValueError("collector manifest records must contain case IDs")
    case_ids = [record["case_id"] for record in records]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("collector manifest has duplicate case IDs")
    disk_case_ids = {path.name for path in run_root.iterdir() if path.is_dir()}
    unknown = disk_case_ids - set(case_ids)
    if unknown:
        raise ValueError(f"run root contains case directories absent from collector manifest: {', '.join(sorted(unknown))}")
    return {
        "sha256": sha256(path),
        "collection_id": value.get("collection_id"),
        "inference_route": value.get("inference_route"),
        "provider": value.get("provider"),
        "model": value.get("model"),
        "tool_catalog": value.get("tool_catalog"),
        "wall_timeout_seconds": value.get("wall_timeout_seconds"),
        "record_count": len(records),
    }


def prepare(run_root: Path, matrix_path: Path, trials: int, arm: str, catalog: str = "extended") -> dict[str, Any]:
    if trials < 1:
        raise ValueError("trials must be at least 1")
    matrix = COVERAGE.load_matrix(matrix_path)
    manifest = collector_manifest(run_root, arm, trials)
    inventory = SUMMARY.summarize(run_root, catalog)
    coverage = COVERAGE.report(matrix, matrix_path, run_root, trials, arm)
    # Retain only public scenario IDs and tool-name metadata from coverage.
    scenario_reports = [
        {
            "scenario_id": scenario["scenario_id"],
            "expected_trials": scenario["expected_trials"],
            "signal_matched_trials": scenario["signal_matched_trials"],
            "trials": [
                {
                    key: trial[key]
                    for key in ("case_id", "trial", "status", "expected_signals", "signal_match_mode", "observed_tools")
                    if key in trial
                }
                for trial in scenario["trials"]
            ],
        }
        for scenario in coverage["scenarios"]
    ]
    return {
        "schema_version": "collection-review-dossier-v1",
        "run_root": str(run_root),
        "arm": arm,
        "catalog": catalog,
        "matrix_sha256": sha256(matrix_path),
        "collector_manifest": manifest,
        "inventory": inventory,
        "signal_coverage": {
            "all_expected_signals_matched": coverage["all_expected_signals_matched"],
            "scenarios": scenario_reports,
        },
        "notice": (
            "Metadata-only review preparation. Human review of raw fictional trace content, "
            "formal trace promotion, and NeMo Insights Intake remain separate required steps."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, default=ROOT / "experiments" / "fidelity-matrix.json")
    parser.add_argument("--trials", type=int, required=True)
    parser.add_argument("--arm", choices=["baseline", "candidate"], default="baseline")
    parser.add_argument("--catalog", choices=["focused", "extended"], default="extended")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        dossier = prepare(args.run_root, args.matrix, args.trials, args.arm, args.catalog)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dossier, indent=2) + "\n")
    print(f"Wrote metadata-only collection review dossier: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

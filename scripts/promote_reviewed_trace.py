#!/usr/bin/env python3
"""Promote one reviewed real ATOF artifact into the public trace bundle.

Promotion is intentionally an explicit, reviewer-attributed act.  This tool
does not inspect or sanitize trace contents and must only be used after a human
has reviewed the proposed export against the fictional-fixture boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parents[1]
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def require_safe_id(label: str, value: str) -> None:
    if not SAFE_ID.fullmatch(value):
        raise ValueError(f"{label} must contain only letters, numbers, dot, underscore, or hyphen")


def relative_to_root(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve()))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", type=Path, required=True, help="Ignored run directory created by run_hermes_case.sh")
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--run-id", required=True, help="Stable checked-in provenance group ID")
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--reviewed-at", default=utc_now())
    parser.add_argument("--statement", default="All checked-in trace content is fictional and contains no PA or enterprise data.")
    parser.add_argument("--approve-fictional-content", action="store_true", help="Required acknowledgement after human review")
    parser.add_argument("--manifest", type=Path, default=ROOT / "traces" / "manifest.json")
    args = parser.parse_args()
    if not args.approve_fictional_content:
        raise SystemExit("error: --approve-fictional-content is required after human public-data review")
    for label, value in (("trace ID", args.trace_id), ("run ID", args.run_id)):
        require_safe_id(label, value)
    if not args.reviewer.strip() or not args.statement.strip():
        raise SystemExit("error: reviewer and review statement must be non-empty")

    source_run = args.source_run.resolve()
    provenance_source = source_run / "collection-provenance.json"
    atof_paths = sorted((source_run / "relay" / "atof").glob("*.jsonl"))
    if not provenance_source.is_file():
        raise SystemExit(f"error: source run has no provenance: {provenance_source}")
    if len(atof_paths) != 1:
        raise SystemExit("error: source run must contain exactly one ATOF .jsonl artifact")
    provenance = load_json(provenance_source)
    if provenance.get("schema_version") != "run-provenance-v1":
        raise SystemExit("error: unsupported source-run provenance")

    arm = provenance.get("harness", {}).get("arm")
    if arm not in {"baseline", "candidate"}:
        raise SystemExit("error: source provenance is missing a baseline/candidate arm")
    trace_destination = ROOT / "traces" / arm / f"{args.trace_id}.atof.jsonl"
    provenance_destination = ROOT / "traces" / "provenance" / f"{args.run_id}.json"
    if trace_destination.exists():
        raise SystemExit(f"error: refusing to overwrite existing trace: {trace_destination}")
    if args.manifest.exists():
        manifest = load_json(args.manifest)
    else:
        manifest = {
            "schema_version": "1.2",
            "collection_status": "pending",
            "fixture": {
                "world_version": "v1",
                "path": "fixtures/world-v1.json",
                "sha256": sha256(ROOT / "fixtures" / "world-v1.json"),
            },
            "runs": [],
            "public_data_review": {"approved": False, "reviewer": None, "reviewed_at": None, "statement": ""},
            "traces": [],
        }
    if manifest.get("schema_version") != "1.2":
        raise SystemExit("error: manifest must use schema_version 1.2")
    if any(trace.get("trace_id") == args.trace_id for trace in manifest.get("traces", [])):
        raise SystemExit(f"error: trace ID already exists in manifest: {args.trace_id}")

    runs = manifest.setdefault("runs", [])
    existing_run = next((run for run in runs if run.get("id") == args.run_id), None)
    # The eventual provenance path/hash are deterministic from the source file;
    # validate the run mapping before copying either artifact into the bundle.
    candidate_run = {
        "id": args.run_id,
        "agent_runtime": provenance.get("collection", {}).get("mode", "local-hermes"),
        "agent_revision": provenance["harness"]["hermes_revision"],
        "harness_profile": f"{provenance['harness']['arm']}-system-prompt",
        "harness_profile_sha256": provenance["harness"]["profile_sha256"],
        "model": provenance["inference"]["model"],
        "sampling": {},
        "relay_format": "ATOF",
        "tool_catalog": provenance["harness"]["tool_catalog"],
        "provenance_path": relative_to_root(provenance_destination),
        "provenance_sha256": sha256(provenance_source),
    }
    if existing_run is None:
        runs.append(candidate_run)
    elif existing_run != candidate_run:
        raise SystemExit(f"error: run ID maps to different provenance: {args.run_id}")
    trace_destination.parent.mkdir(parents=True, exist_ok=True)
    provenance_destination.parent.mkdir(parents=True, exist_ok=True)
    if provenance_destination.exists() and provenance_destination.read_bytes() != provenance_source.read_bytes():
        raise SystemExit(f"error: refusing to replace distinct provenance: {provenance_destination}")
    if not provenance_destination.exists():
        shutil.copyfile(provenance_source, provenance_destination)
    shutil.copyfile(atof_paths[0], trace_destination)
    manifest.setdefault("traces", []).append(
        {
            "trace_id": args.trace_id,
            "case_id": args.case_id,
            "run_id": args.run_id,
            "path": relative_to_root(trace_destination),
            "sha256": sha256(trace_destination),
        }
    )
    manifest["collection_status"] = "complete"
    manifest["public_data_review"] = {
        "approved": True,
        "reviewer": args.reviewer,
        "reviewed_at": args.reviewed_at,
        "statement": args.statement,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Promoted reviewed trace: {trace_destination}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError) as error:
        raise SystemExit(f"error: {error}")

#!/usr/bin/env python3
"""Validate a sanitized real-trace manifest without inspecting trace content."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parents[1]
REQUIRED_RUN_FIELDS = {
    "id",
    "agent_runtime",
    "agent_revision",
    "harness_profile",
    "model",
    "sampling",
    "relay_format",
    "tool_catalog",
    "provenance_path",
    "provenance_sha256",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repository_path(root: Path, raw_path: Any) -> Path | None:
    """Resolve a manifest path only when it remains inside the repository."""
    if not isinstance(raw_path, str) or not raw_path:
        return None
    candidate = (root / raw_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def validate(manifest: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != "1.2":
        errors.append("unsupported or missing schema_version")
    if manifest.get("collection_status") not in {"pending", "complete"}:
        errors.append("collection_status must be pending or complete")

    fixture = manifest.get("fixture", {})
    fixture_path = repository_path(root, fixture.get("path"))
    if fixture_path is None:
        errors.append("fixture path must be a repository-relative path")
        fixture_path = root / "__invalid_fixture_path__"
    if not fixture_path.is_file():
        errors.append("fixture path is missing")
    elif fixture.get("sha256") != sha256(fixture_path):
        errors.append("fixture sha256 does not match the checked-in fixture")

    runs = manifest.get("runs")
    if not isinstance(runs, list) or not runs:
        errors.append("runs must be a non-empty list")
        runs = []
    run_ids: set[str] = set()
    for run in runs:
        if not isinstance(run, dict):
            errors.append("each run must be an object")
            continue
        missing_run_fields = sorted(REQUIRED_RUN_FIELDS - set(run))
        if missing_run_fields:
            errors.append(f"run is missing fields: {', '.join(missing_run_fields)}")
            continue
        run_id = run["id"]
        if not isinstance(run_id, str) or not run_id or run_id in run_ids:
            errors.append(f"run ID missing or duplicated: {run_id!r}")
        run_ids.add(run_id)
        for field in ("agent_revision", "model"):
            if str(run.get(field, "")).startswith("REPLACE_WITH_"):
                errors.append(f"run {run_id}.{field} has not been pinned")
        if not isinstance(run.get("sampling"), dict):
            errors.append(f"run {run_id}.sampling must be an object")
        if run.get("relay_format") not in {"ATOF", "ATOF-normalized-ATIF-v1.7"}:
            errors.append(
                f"run {run_id}.relay_format must be ATOF or ATOF-normalized-ATIF-v1.7"
            )
        if run.get("tool_catalog") not in {"focused", "extended"}:
            errors.append(f"run {run_id}.tool_catalog must be focused or extended")
        provenance_path = repository_path(root, run.get("provenance_path"))
        if provenance_path is None:
            errors.append(f"run {run_id}.provenance_path must be repository-relative")
        elif not provenance_path.is_file():
            errors.append(f"run {run_id}.provenance_path is missing")
        elif run.get("provenance_sha256") != sha256(provenance_path):
            errors.append(f"run {run_id}.provenance_sha256 does not match")

    review = manifest.get("public_data_review", {})
    if manifest.get("collection_status") == "complete" and not review.get("approved"):
        errors.append("complete collection requires public_data_review.approved=true")
    if manifest.get("collection_status") == "complete":
        for field in ("reviewer", "reviewed_at"):
            if not isinstance(review.get(field), str) or not review[field]:
                errors.append(f"complete collection requires public_data_review.{field}")

    seen_ids: set[str] = set()
    for trace in manifest.get("traces", []):
        trace_id = trace.get("trace_id")
        if not trace_id or trace_id in seen_ids:
            errors.append(f"trace ID missing or duplicated: {trace_id!r}")
        seen_ids.add(trace_id)
        trace_path = repository_path(root, trace.get("path"))
        if trace_path is None:
            errors.append(f"trace path must be repository-relative for {trace_id}")
            trace_path = root / "__invalid_trace_path__"
        if not trace_path.is_file():
            errors.append(f"trace file missing for {trace_id}: {trace.get('path')}")
        elif trace.get("sha256") != sha256(trace_path):
            errors.append(f"trace sha256 does not match for {trace_id}")
        if not trace.get("case_id"):
            errors.append(f"trace {trace_id} is missing case_id")
        if trace.get("run_id") not in run_ids:
            errors.append(f"trace {trace_id} has an unknown or missing run_id: {trace.get('run_id')!r}")
    if manifest.get("collection_status") == "complete" and not manifest.get("traces"):
        errors.append("complete collection requires at least one trace")
    return errors


def main() -> int:
    manifest_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "traces" / "manifest.json"
    if not manifest_path.is_file():
        print(f"No manifest found at {manifest_path}; use traces/manifest.template.json after real collection.")
        return 2
    errors = validate(json.loads(manifest_path.read_text()), ROOT)
    if errors:
        print("Trace manifest validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Trace manifest validation passed: traces={len(json.loads(manifest_path.read_text()).get('traces', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

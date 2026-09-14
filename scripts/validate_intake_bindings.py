#!/usr/bin/env python3
"""Validate the reviewed-trace to NeMo Intake reference bridge.

This maps immutable checked-in ATOF artifacts to the ``intake://`` references
that NeMo Insights and Eval Author consume. It deliberately does not upload
traces, invent trace IDs, or contact a Platform service.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_repo_path(raw_path: Any, root: Path) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path:
        return None
    candidate = (root / raw_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def validate(bindings: dict[str, Any], manifest: dict[str, Any], manifest_path: Path, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if bindings.get("schema_version") != "intake-bindings-v1":
        errors.append("unsupported or missing bindings schema_version")
    expected_manifest_path = resolve_repo_path(bindings.get("trace_manifest_path"), root)
    if expected_manifest_path is None or expected_manifest_path != manifest_path.resolve():
        errors.append("trace_manifest_path must identify the supplied repository manifest")
    elif bindings.get("trace_manifest_sha256") != sha256(manifest_path):
        errors.append("trace_manifest_sha256 does not match the supplied manifest")
    if not isinstance(bindings.get("workspace"), str) or not bindings["workspace"].strip():
        errors.append("workspace must be a non-empty string")
    if not isinstance(bindings.get("agent_name"), str) or not bindings["agent_name"].strip():
        errors.append("agent_name must be a non-empty string")

    manifest_traces = {trace.get("trace_id"): trace for trace in manifest.get("traces", []) if isinstance(trace, dict)}
    entries = bindings.get("bindings")
    if not isinstance(entries, list) or not entries:
        errors.append("bindings must be a non-empty list")
        return errors
    seen_trace_ids: set[str] = set()
    seen_refs: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("each binding must be an object")
            continue
        trace_id = entry.get("trace_id")
        trace = manifest_traces.get(trace_id)
        if not isinstance(trace_id, str) or trace is None:
            errors.append(f"binding references unknown trace_id: {trace_id!r}")
            continue
        if trace_id in seen_trace_ids:
            errors.append(f"duplicate binding for trace_id: {trace_id}")
        seen_trace_ids.add(trace_id)
        if entry.get("trace_sha256") != trace.get("sha256"):
            errors.append(f"binding trace_sha256 does not match manifest for {trace_id}")
        intake_ref = entry.get("intake_trace_ref")
        if not isinstance(intake_ref, str) or not intake_ref.startswith("intake://") or len(intake_ref) <= len("intake://"):
            errors.append(f"binding needs an intake:// trace reference for {trace_id}")
        elif intake_ref in seen_refs:
            errors.append(f"duplicate intake trace reference: {intake_ref}")
        else:
            seen_refs.add(intake_ref)
    return errors


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: validate_intake_bindings.py <bindings.json> <trace-manifest.json>")
        return 2
    bindings_path, manifest_path = (Path(value).resolve() for value in sys.argv[1:])
    if not bindings_path.is_file() or not manifest_path.is_file():
        print("Bindings and trace manifest files must both exist.")
        return 2
    errors = validate(json.loads(bindings_path.read_text()), json.loads(manifest_path.read_text()), manifest_path)
    if errors:
        print("Intake binding validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Intake binding validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

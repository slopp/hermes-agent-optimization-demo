#!/usr/bin/env python3
"""Validate that a candidate harness run follows from reviewed trace evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from validate_trace_derived_suite import validate as validate_suite


ROOT = Path(__file__).parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_file(raw_path: Any) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path:
        return None
    path = (ROOT / raw_path).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError:
        return None
    return path if path.is_file() else None


def validate(manifest: dict[str, Any], suite: dict[str, Any], suite_path: Path) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != "candidate-experiment-v1":
        errors.append("schema_version must be candidate-experiment-v1")
    if manifest.get("status") != "approved_for_test":
        errors.append("candidate experiment must be approved_for_test")
    if not manifest.get("reviewer") or not manifest.get("approved_at"):
        errors.append("candidate experiment requires reviewer and approved_at")
    suite_errors = validate_suite(suite)
    if suite_errors:
        errors.extend(f"trace-derived suite is invalid: {error}" for error in suite_errors)
        return errors
    if manifest.get("insight_ref") != suite["generation"].get("insight_ref"):
        errors.append("insight_ref must match the frozen trace-derived suite")
    expected_suite = repo_file(manifest.get("trace_derived_suite_path"))
    if expected_suite is None or expected_suite != suite_path.resolve():
        errors.append("trace_derived_suite_path must identify the supplied suite inside the repository")
    elif manifest.get("trace_derived_suite_sha256") != sha256(suite_path):
        errors.append("trace_derived_suite_sha256 does not match the supplied suite")
    profile = repo_file(manifest.get("candidate_profile_path"))
    if profile is None:
        errors.append("candidate_profile_path must identify an existing repository file")
    elif manifest.get("candidate_profile_sha256") != sha256(profile):
        errors.append("candidate_profile_sha256 does not match the candidate profile")
    card = repo_file(manifest.get("pattern_card_path"))
    if card is None:
        errors.append("pattern_card_path must identify an existing repository file")
    elif "Status: `eval-frozen`" not in card.read_text() and "Status: `candidate-tested`" not in card.read_text():
        errors.append("pattern card must be at least eval-frozen before a candidate run")
    cases = manifest.get("case_ids")
    if not isinstance(cases, dict):
        errors.append("case_ids must map trace_derived and held_out case IDs")
        return errors
    expected = {
        kind: {case["id"] for case in suite["cases"] if case.get("case_kind") == kind}
        for kind in ("trace_derived", "held_out")
    }
    for kind, expected_ids in expected.items():
        actual_ids = cases.get(kind)
        if not isinstance(actual_ids, list) or set(actual_ids) != expected_ids:
            errors.append(f"case_ids.{kind} must exactly match the frozen suite's {kind} cases")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--suite", type=Path, required=True)
    args = parser.parse_args()
    if not args.manifest.is_file() or not args.suite.is_file():
        parser.error("manifest and --suite must both exist")
    errors = validate(json.loads(args.manifest.read_text()), json.loads(args.suite.read_text()), args.suite)
    if errors:
        print("Candidate experiment validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Candidate experiment validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate the trace-derived development and held-out suite contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def validate(suite: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    version = suite.get("suite_version")
    if version != "2.0":
        errors.append("suite_version must be 2.0")
    generation = suite.get("generation", {})
    local_trace_workflow = version == "2.0"
    if local_trace_workflow:
        if generation.get("method") != "codex-guided-nemo-eval-author":
            errors.append("generation.method must record the Codex-guided Eval Author workflow")
        insight_refs = generation.get("insight_refs")
        if not isinstance(insight_refs, list) or not insight_refs or not all(
            str(ref).startswith("insights://") for ref in insight_refs
        ):
            errors.append("generation.insight_refs must contain insights:// references")
        if generation.get("review_status") != "reference_tasks_checked_in":
            errors.append("v2 suite must identify checked-in reference tasks")
        if generation.get("source_corpus") != "traces/world-v2/corpus/index.json":
            errors.append("v2 suite requires the checked-in source corpus")
        if generation.get("source_trace_count") != 36:
            errors.append("v2 suite requires all 36 source traces")

    cases = suite.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append("suite requires at least one case")
        return errors
    all_case_ids = {case.get("id") for case in cases if isinstance(case, dict)}
    case_kinds = {case.get("id"): case.get("case_kind") for case in cases if isinstance(case, dict)}
    case_ids: set[str] = set()
    for case in cases:
        case_id = case.get("id")
        if not case_id or case_id in case_ids:
            errors.append(f"case ID missing or duplicated: {case_id!r}")
        case_ids.add(case_id)
        provenance = case.get("provenance", {})
        local_trace_ref = provenance.get("trace_ref")
        case_kind = case.get("case_kind")
        if case_kind not in {"trace_derived", "held_out"}:
            errors.append(f"case {case_id} case_kind must be trace_derived or held_out")
        elif case_kind == "trace_derived" and local_trace_workflow:
            if not isinstance(local_trace_ref, str) or not local_trace_ref.endswith(
                ".atif.json"
            ):
                errors.append(f"trace-derived case {case_id} needs a local ATIF trace_ref")
        elif case_kind == "held_out":
            parents = provenance.get("held_out_from_case_ids")
            if not isinstance(parents, list) or not parents or not all(
                parent in all_case_ids and parent != case_id and case_kinds.get(parent) == "trace_derived"
                for parent in parents
            ):
                errors.append(f"held-out case {case_id} needs existing held_out_from_case_ids")
        if case_kind == "trace_derived" and provenance.get("harbor_task_ref") != (
            f"evals/harbor-tasks-v2/{case_id}"
        ):
            errors.append(f"case {case_id} needs its checked-in Harbor task reference")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", type=Path)
    args = parser.parse_args()
    errors = validate(json.loads(args.suite.read_text()))
    if errors:
        print("Trace-derived suite validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Trace-derived suite validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

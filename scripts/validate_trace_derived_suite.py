#!/usr/bin/env python3
"""Validate the reviewed Eval Author output retained for reproducible A/B runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:  # Support both ``python scripts/...`` and package-style test imports.
    from scripts.validate_intake_bindings import validate as validate_intake_bindings
except ModuleNotFoundError:  # pragma: no cover - direct script execution path
    from validate_intake_bindings import validate as validate_intake_bindings


def validate(suite: dict[str, Any], allowed_trace_refs: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    version = suite.get("suite_version")
    if version not in {"1.1", "2.0"}:
        errors.append("suite_version must be 1.1 or 2.0")
    generation = suite.get("generation", {})
    local_trace_workflow = version == "2.0"
    if local_trace_workflow:
        if generation.get("method") != "nemo-eval-author-trace-environment":
            errors.append("generation.method must record the Eval Author trace environment")
        insight_refs = generation.get("insight_refs")
        if not isinstance(insight_refs, list) or not insight_refs or not all(
            str(ref).startswith("insights://") for ref in insight_refs
        ):
            errors.append("generation.insight_refs must contain insights:// references")
        if generation.get("review_status") not in {
            "agent_contextual_privacy_review_complete",
            "agent_publication_review_complete",
            "human_publication_review_complete",
        }:
            errors.append("v2 suite requires completed contextual privacy review")
        if not generation.get("source_batch"):
            errors.append("v2 suite requires generation.source_batch")
    else:
        if generation.get("method") != "nemo-eval-author-library-runner":
            errors.append("generation.method must record the Eval Author library runner")
        if not str(generation.get("insight_ref", "")).startswith("insights://"):
            errors.append("generation.insight_ref must be an insights:// reference")
        if generation.get("review_status") != "approved":
            errors.append("trace-derived suite must be explicitly approved before use")
        if not generation.get("reviewer") or not generation.get("frozen_at"):
            errors.append("approved suite requires reviewer and frozen_at")

    case_ids: set[str] = set()
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
        trace_refs = provenance.get("trace_refs")
        local_trace_ref = provenance.get("trace_ref")
        case_kind = case.get("case_kind")
        if case_kind not in {"trace_derived", "held_out"}:
            errors.append(f"case {case_id} case_kind must be trace_derived or held_out")
        elif case_kind == "trace_derived":
            if local_trace_workflow:
                if not isinstance(local_trace_ref, str) or not local_trace_ref.endswith(
                    ".atif.json"
                ):
                    errors.append(f"trace-derived case {case_id} needs a local ATIF trace_ref")
            elif (
                not isinstance(trace_refs, list)
                or not trace_refs
                or not all(str(ref).startswith("intake://") for ref in trace_refs)
            ):
                errors.append(
                    f"trace-derived case {case_id} needs one or more intake:// trace_refs"
                )
        elif case_kind == "held_out":
            parents = provenance.get("held_out_from_case_ids")
            if not isinstance(parents, list) or not parents or not all(
                parent in all_case_ids and parent != case_id and case_kinds.get(parent) == "trace_derived"
                for parent in parents
            ):
                errors.append(f"held-out case {case_id} needs existing held_out_from_case_ids")
        if case_kind == "trace_derived" and allowed_trace_refs is not None and isinstance(trace_refs, list):
            unknown_refs = sorted(set(trace_refs) - allowed_trace_refs)
            if unknown_refs:
                errors.append(f"case {case_id} references Intake traces not bound to the reviewed bundle: {', '.join(unknown_refs)}")
        if case_kind == "trace_derived" and not provenance.get("eval_author_case_ref"):
            errors.append(f"case {case_id} needs eval_author_case_ref")
        if (
            local_trace_workflow
            and generation.get("review_status") == "agent_publication_review_complete"
            and case_kind == "trace_derived"
            and not str(provenance.get("eval_author_product_ref", "")).endswith("/result.json")
        ):
            errors.append(f"trace-derived case {case_id} needs an exported Eval Author product")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", type=Path)
    parser.add_argument("--intake-bindings", type=Path, help="Mapping of reviewed trace IDs to Intake refs")
    parser.add_argument("--trace-manifest", type=Path, help="Required with --intake-bindings")
    args = parser.parse_args()
    if bool(args.intake_bindings) != bool(args.trace_manifest):
        parser.error("--intake-bindings and --trace-manifest must be supplied together")
    allowed_refs: set[str] | None = None
    if args.intake_bindings:
        bindings = json.loads(args.intake_bindings.read_text())
        manifest = json.loads(args.trace_manifest.read_text())
        binding_errors = validate_intake_bindings(bindings, manifest, args.trace_manifest.resolve())
        if binding_errors:
            print("Trace-derived suite validation failed because Intake bindings are invalid:")
            for error in binding_errors:
                print(f"- {error}")
            return 1
        allowed_refs = {entry["intake_trace_ref"] for entry in bindings["bindings"]}
    errors = validate(json.loads(args.suite.read_text()), allowed_refs)
    if errors:
        print("Trace-derived suite validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Trace-derived suite validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

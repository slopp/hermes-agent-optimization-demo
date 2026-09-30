#!/usr/bin/env python3
"""Validate the saved production-trace → Insights → Eval Author → A/B chain."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_task_products import validate as validate_task_products


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"artifact-chain validation failed: {message}")


def validate(root: Path, *, require_review: bool = True) -> None:
    chain_path = root / "results" / "artifact-chain.json"
    chain = json.loads(chain_path.read_text(encoding="utf-8"))
    require(
        chain.get("schema") == "hermes-agent-optimization-artifact-chain-v3",
        "unsupported artifact chain schema",
    )
    runtime = chain.get("runtime", {})
    require(runtime.get("agent_sandbox") == "OpenShell", "Hermes must run in OpenShell")
    mcp = runtime.get("mcp", {})
    require(mcp.get("location") == "host_outside_sandbox", "MCP must be hosted outside OpenShell")
    require(mcp.get("transport") == "streamable-http", "measured MCP transport must be Streamable HTTP")
    require(mcp.get("host") == "host.openshell.internal", "unexpected OpenShell host bridge")
    require(set(mcp.get("ports", [])) == {8765}, "MCP ports differ from the OpenShell policy")

    stage_ids: set[str] = set()
    stage_paths: dict[str, Path] = {}
    for stage in chain.get("stages", []):
        stage_id = stage.get("id")
        require(isinstance(stage_id, str) and stage_id not in stage_ids, f"duplicate/invalid stage {stage_id}")
        require(set(stage.get("consumes", [])) <= stage_ids, f"{stage_id} consumes a missing or later stage")
        relative = Path(stage["path"])
        require(not relative.is_absolute() and ".." not in relative.parts, "unsafe artifact path")
        path = root / relative
        require(path.is_file(), f"missing artifact {stage['path']}")
        require(digest(path) == stage.get("sha256"), f"digest drift in {stage['path']}")
        stage_ids.add(stage_id)
        stage_paths[stage_id] = path

    required_stages = {
        "production_corpus", "production_insights", "eval_suite",
        "baseline_development_traces", "baseline_development_insights",
        "candidate_proposal", "candidate_profile", "measured_ab",
    }
    require(required_stages <= stage_ids, f"missing chain stages: {sorted(required_stages - stage_ids)}")

    corpus = json.loads(stage_paths["production_corpus"].read_text(encoding="utf-8"))
    source_traces = corpus.get("traces", [])
    require(36 <= len(source_traces) <= 48, "production trace count must be 36–48")
    prompt_values = [str(record.get("prompt", "")).strip().casefold() for record in source_traces]
    require(all(prompt_values) and len(set(prompt_values)) == len(prompt_values), "source prompts must be nonempty and distinct")
    family_counts = Counter(record.get("behavior_family") for record in source_traces)
    require(len(family_counts) >= 5 and min(family_counts.values()) >= 4, "source corpus lacks family coverage")
    trace_paths = {record.get("path") for record in source_traces}

    suite = json.loads(stage_paths["eval_suite"].read_text(encoding="utf-8"))
    generation = suite.get("generation", {})
    require(generation.get("source_trace_count") == len(source_traces), "suite source denominator differs from corpus")
    review = generation.get("review_status")
    require(review in ("human_reviewed", "pending_human_review"), "invalid suite review state")
    require(not require_review or review == "human_reviewed", "suite requires human task/split review")
    require(generation.get("split_frozen_before_candidate") is True, "suite split was not frozen before candidate design")
    cases = suite.get("cases", [])
    dev_cases = [case for case in cases if case.get("case_kind") == "development"]
    held_cases = [case for case in cases if case.get("case_kind") == "held_out"]
    require(dev_cases and held_cases, "suite needs development and held-out tasks")
    seen_sources: set[str] = set()
    for case in cases:
        provenance = case.get("provenance", {})
        source_ref = provenance.get("trace_ref", "")
        trace_path = Path(source_ref)
        require(not trace_path.is_absolute() and ".." not in trace_path.parts, f"unsafe trace reference in {case.get('id')}")
        require(str(trace_path.relative_to("traces/world-v3/production")) in trace_paths,
                f"case {case.get('id')} source trace is not in the indexed production corpus")
        require(source_ref not in seen_sources, f"source trace reused for {case.get('id')}")
        seen_sources.add(source_ref)
        require(provenance.get("insight_refs"), f"case {case.get('id')} lacks production Insights provenance")
        require(case.get("relevant_experience"), f"case {case.get('id')} lacks relevant experience")

    proof_errors = validate_task_products(root, require_review=require_review)
    require(not proof_errors, "; ".join(proof_errors))
    freeze = json.loads((root / "results/experiment-freeze.json").read_text())
    require(freeze.get("candidate_frozen_before_held_out_execution") is True,
            "candidate was not frozen before held-out execution")
    require(set(freeze.get("development_task_ids", [])) == {case["id"] for case in dev_cases},
            "development membership differs from experiment freeze")
    require(set(freeze.get("held_out_task_ids", [])) == {case["id"] for case in held_cases},
            "held-out membership differs from experiment freeze")
    require(digest(stage_paths["candidate_profile"]) == freeze.get("candidate_profile_sha256"),
            "candidate profile differs from frozen design")

    baseline_bundle_path = stage_paths["baseline_development_traces"]
    baseline_bundle = [
        json.loads(line)
        for line in baseline_bundle_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    counts = Counter(trace.get("attributes", {}).get("logical_case_id") for trace in baseline_bundle)
    require(set(counts) == {case["id"] for case in dev_cases}, "scored baseline bundle task IDs differ from development split")
    attempt_counts = set(counts.values())
    require(len(attempt_counts) == 1 and next(iter(attempt_counts)) >= 3, "baseline dev task attempt counts must match and be K ≥ 3")
    require(all(trace.get("evaluator_results", {}).get("harbor.reward") in (0, 0.0, 1, 1.0) for trace in baseline_bundle),
            "baseline bundle must retain a binary Harbor reward on every trace")

    measured = json.loads(stage_paths["measured_ab"].read_text(encoding="utf-8"))
    require(measured.get("schema") == "hermes-harbor-ab-comparison-v3", "invalid measured A/B schema")
    attempts = measured.get("attempts_per_task_per_arm")
    require(isinstance(attempts, int) and attempts >= 3, "A/B requires at least three attempts per task and arm")
    for split, cases_on_split in (("development", dev_cases), ("held_out", held_cases)):
        record = measured.get(split, {})
        require(record.get("regressed_tasks") == [], f"{split} has per-task regressions or lacks a regression check")
        require(record.get("tasks") == len(cases_on_split), f"{split} task denominator differs from frozen suite")
        require(record.get("attempts_per_task_per_arm") == attempts, f"{split} attempt count differs")
        for arm in ("baseline", "candidate"):
            summary = record.get(arm, {})
            require(summary.get("trials") == len(cases_on_split) * attempts, f"{split}/{arm} trial denominator is incomplete")
            require(summary.get("exceptions") == 0, f"{split}/{arm} contains infrastructure exceptions")
            require(set(summary.get("per_task", {})) == {case["id"] for case in cases_on_split},
                    f"{split}/{arm} per-task results differ from the suite")
    require(measured["development"]["candidate_improved"], "candidate must improve development pass rate")
    require(measured["held_out"]["candidate_improved"], "candidate must improve held-out pass rate")
    require(measured.get("acceptance", {}).get("both_splits_improve") is True, "A/B acceptance must record both-split improvement")

    print(
        "artifact chain valid: "
        f"X={len(source_traces)} source traces → Y={len(cases)} tasks "
        f"({len(dev_cases)} development/{len(held_cases)} held out) → "
        f"K={attempts} attempts → candidate improves both splits"
    )
    if not require_review:
        print("Technical pilot integrity only; this does not establish human task review or readiness.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-unreviewed", action="store_true",
                        help="Check technical pilot integrity without claiming human review.")
    args = parser.parse_args()
    validate(ROOT, require_review=not args.allow_unreviewed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

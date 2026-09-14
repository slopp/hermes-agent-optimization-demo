"""Score recorded agent runs against a frozen eval suite.

An adapter can extract ``calls``, ``final_answer``, and ``outbox`` from a real
Hermes/Relay trace. This module purposefully does not generate model output or
invent trajectories.
"""

from __future__ import annotations

from typing import Any

from .verify import verify_case


def suite_cases(suite: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    """Accept a legacy bare case list or a provenance-bearing frozen suite."""
    if isinstance(suite, list):
        return suite
    if isinstance(suite, dict) and isinstance(suite.get("cases"), list):
        return suite["cases"]
    raise ValueError("suite must be a case list or an object containing cases")


def score_runs(suite: list[dict[str, Any]] | dict[str, Any], runs: list[dict[str, Any]]) -> dict[str, Any]:
    cases = suite_cases(suite)
    case_by_id = {case["id"]: case for case in cases}
    seen_case_ids: set[str] = set()
    results: list[dict[str, Any]] = []

    for run in runs:
        case_id = run.get("case_id")
        if case_id not in case_by_id:
            raise ValueError(f"run references unknown case: {case_id!r}")
        if case_id in seen_case_ids:
            raise ValueError(f"multiple runs for case: {case_id!r}")
        seen_case_ids.add(case_id)
        verdict = verify_case(
            case_by_id[case_id],
            run.get("calls", []),
            run.get("final_answer", ""),
            run.get("outbox", []),
            run.get("tool_results"),
        )
        results.append(
            {
                "case_id": case_id,
                "case_kind": case_by_id[case_id].get("case_kind", "unclassified"),
                "tool_call_count": len(run.get("calls", [])),
                **verdict,
            }
        )

    missing_case_ids = sorted(set(case_by_id) - seen_case_ids)
    if missing_case_ids:
        raise ValueError(f"runs are missing suite cases: {', '.join(missing_case_ids)}")

    count = len(results)
    dimension_rates = {
        dimension: sum(result["dimensions"][dimension] for result in results) / count if count else 0.0
        for dimension in ("trajectory", "answer", "state")
    }
    total_tool_calls = sum(result["tool_call_count"] for result in results)
    return {
        "case_count": count,
        "passed_case_count": sum(result["passed"] for result in results),
        "pass_rate": sum(result["passed"] for result in results) / count if count else 0.0,
        "dimension_rates": dimension_rates,
        "total_tool_calls": total_tool_calls,
        "mean_tool_calls": total_tool_calls / count if count else 0.0,
        "by_case_kind": _aggregate_case_kinds(results),
        "results": results,
    }


def _aggregate_case_kinds(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Keep trace-derived and held-out behavior visibly separate in reports."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        groups.setdefault(result["case_kind"], []).append(result)
    return {
        kind: {
            "case_count": len(group),
            "passed_case_count": sum(item["passed"] for item in group),
            "pass_rate": sum(item["passed"] for item in group) / len(group),
            "dimension_rates": {
                dimension: sum(item["dimensions"][dimension] for item in group) / len(group)
                for dimension in ("trajectory", "answer", "state")
            },
            "mean_tool_calls": sum(item["tool_call_count"] for item in group) / len(group),
        }
        for kind, group in sorted(groups.items())
    }


def compare_reports(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Return deltas without deciding that a candidate is safe to ship."""
    if baseline["case_count"] != candidate["case_count"]:
        raise ValueError("cannot compare reports with different case counts")
    by_case_kind: dict[str, dict[str, float]] = {}
    all_kinds = set(baseline["by_case_kind"]) | set(candidate["by_case_kind"])
    for kind in sorted(all_kinds):
        if kind not in baseline["by_case_kind"] or kind not in candidate["by_case_kind"]:
            raise ValueError(f"cannot compare reports with different case kinds: {kind}")
        baseline_kind, candidate_kind = baseline["by_case_kind"][kind], candidate["by_case_kind"][kind]
        by_case_kind[kind] = {
            "pass_rate_delta": candidate_kind["pass_rate"] - baseline_kind["pass_rate"],
            **{
                f"{dimension}_delta": candidate_kind["dimension_rates"][dimension]
                - baseline_kind["dimension_rates"][dimension]
                for dimension in ("trajectory", "answer", "state")
            },
            "mean_tool_calls_delta": candidate_kind["mean_tool_calls"] - baseline_kind["mean_tool_calls"],
        }
    report = {
        "case_count": baseline["case_count"],
        "pass_rate_delta": candidate["pass_rate"] - baseline["pass_rate"],
        "trajectory_delta": candidate["dimension_rates"]["trajectory"] - baseline["dimension_rates"]["trajectory"],
        "answer_delta": candidate["dimension_rates"]["answer"] - baseline["dimension_rates"]["answer"],
        "state_delta": candidate["dimension_rates"]["state"] - baseline["dimension_rates"]["state"],
        "mean_tool_calls_delta": candidate["mean_tool_calls"] - baseline["mean_tool_calls"],
        "by_case_kind": by_case_kind,
    }
    held_out = by_case_kind.get("held_out")
    report["claim_gate"] = {
        "held_out_cases_present": bool(held_out),
        "held_out_pass_rate_improved": bool(held_out and held_out["pass_rate_delta"] > 0),
        "no_aggregate_guardrail_regression": all(report[f"{dimension}_delta"] >= 0 for dimension in ("trajectory", "answer", "state")),
        "eligible_to_claim_measured_improvement": bool(
            held_out
            and held_out["pass_rate_delta"] > 0
            and all(report[f"{dimension}_delta"] >= 0 for dimension in ("trajectory", "answer", "state"))
        ),
    }
    return report

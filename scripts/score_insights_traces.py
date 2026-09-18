#!/usr/bin/env python3
"""Score canonical standalone-Insights traces against the flywheel eval set."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

MCP_PREFIXES = ("mcp__pa_style_enterprise__", "mcp__enterprise_world__")
TERMINAL_FAILURE_MARKERS = (
    "context length exceeded",
    "api call failed after",
    "service temporarily overloaded",
)


def canonical_tool_name(name: Any) -> str:
    if not isinstance(name, str):
        return str(name or "")
    for prefix in MCP_PREFIXES:
        if name.startswith(prefix):
            domain, separator, operation = name[len(prefix) :].partition("_")
            return f"{domain}.{operation}" if separator else domain
    return name


def score_trace(trace: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    expected = case["expectations"]
    tools = [canonical_tool_name(span.get("tool_name")) for span in trace["root_spans"]]
    observed = Counter(tools)
    required = Counter(expected.get("required_tools", []))
    missing_tools = [
        name
        for name, count in required.items()
        for _ in range(max(0, count - observed.get(name, 0)))
    ]
    forbidden_tools = sorted(set(expected.get("forbidden_tools", [])) & set(tools))
    answer = str(trace.get("attributes", {}).get("final_answer") or "")
    missing_facts = [
        fact for fact in expected.get("required_facts", []) if fact.lower() not in answer.lower()
    ]
    terminal_failure = next(
        (marker for marker in TERMINAL_FAILURE_MARKERS if marker in answer.lower()), None
    )
    if trace.get("attributes", {}).get("turn_outcome") == "failed":
        terminal_failure = terminal_failure or "turn_outcome:failed"
    trajectory_pass = not missing_tools and not forbidden_tools
    answer_pass = not missing_facts and terminal_failure is None
    return {
        "trace_id": trace["id"],
        "case_id": case["id"],
        "passed": trajectory_pass and answer_pass,
        "trajectory_pass": trajectory_pass,
        "answer_pass": answer_pass,
        "missing_tools": missing_tools,
        "forbidden_tools": forbidden_tools,
        "missing_facts": missing_facts,
        "terminal_failure": terminal_failure,
        "infrastructure_valid": trace.get("attributes", {}).get(
            "infrastructure_valid", True
        ),
        "tool_call_count": len(tools),
        "local_or_session_call_share": trace.get("attributes", {})
        .get("metrics", {})
        .get("local_or_session_call_share"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--arm", action="append", required=True, metavar="NAME=TRACE_JSONL")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--valid-only",
        action="store_true",
        help="Exclude turns containing any recorded provider error from score aggregates.",
    )
    parser.add_argument(
        "--trials-per-case",
        type=int,
        help="Use the first N valid trials per observed case and reject incomplete cases.",
    )
    args = parser.parse_args()

    suite = json.loads(args.suite.read_text())
    cases = {case["id"]: case for case in suite["cases"]}
    report: dict[str, Any] = {"schema_version": "flywheel-ab-report-v1", "arms": {}}
    for arm_spec in args.arm:
        name, separator, raw_path = arm_spec.partition("=")
        if not separator or not name or not raw_path:
            parser.error("--arm must be NAME=TRACE_JSONL")
        traces = [
            json.loads(line) for line in Path(raw_path).read_text().splitlines() if line.strip()
        ]
        results = []
        excluded = []
        excess_valid = []
        selected_by_case: Counter[str] = Counter()
        encountered_cases: set[str] = set()
        for trace in traces:
            case_id = trace.get("attributes", {}).get("logical_case_id")
            if case_id in cases:
                encountered_cases.add(case_id)
                result = score_trace(trace, cases[case_id])
                if args.valid_only and not result["infrastructure_valid"]:
                    excluded.append(result)
                elif (
                    args.trials_per_case is not None
                    and selected_by_case[case_id] >= args.trials_per_case
                ):
                    excess_valid.append(result)
                else:
                    results.append(result)
                    selected_by_case[case_id] += 1
        if args.trials_per_case is not None:
            incomplete = {
                case_id: selected_by_case[case_id]
                for case_id in sorted(encountered_cases)
                if selected_by_case[case_id] < args.trials_per_case
            }
            if incomplete:
                raise SystemExit(
                    f"arm {name!r} has fewer than {args.trials_per_case} valid trials: "
                    f"{incomplete}"
                )
        if not results:
            raise SystemExit(f"arm {name!r} contains no trace matching the suite")
        by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for result in results:
            by_case[result["case_id"]].append(result)
        report["arms"][name] = {
            "trace_count": len(results),
            "excluded_infrastructure_trace_count": len(excluded),
            "excluded_excess_valid_trace_count": len(excess_valid),
            "pass_rate": sum(result["passed"] for result in results) / len(results),
            "trajectory_pass_rate": sum(result["trajectory_pass"] for result in results)
            / len(results),
            "answer_pass_rate": sum(result["answer_pass"] for result in results) / len(results),
            "mean_tool_calls": mean(result["tool_call_count"] for result in results),
            "cases": {
                case_id: {
                    "trials": len(case_results),
                    "pass_rate": sum(item["passed"] for item in case_results) / len(case_results),
                    "mean_tool_calls": mean(item["tool_call_count"] for item in case_results),
                }
                for case_id, case_results in sorted(by_case.items())
            },
            "results": results,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({name: data | {"results": "omitted"} for name, data in report["arms"].items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

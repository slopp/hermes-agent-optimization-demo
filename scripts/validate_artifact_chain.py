#!/usr/bin/env python3
"""Fail when the tutorial's saved trace-to-result story drifts."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"artifact-chain validation failed: {message}")


def main() -> int:
    chain = load_json("results/artifact-chain.json")
    stage_ids: set[str] = set()
    for stage in chain["stages"]:
        stage_id = stage["id"]
        require(stage_id not in stage_ids, f"duplicate stage {stage_id}")
        for dependency in stage.get("consumes", []):
            require(dependency in stage_ids, f"{stage_id} consumes unknown/later {dependency}")
        artifact = ROOT / stage["path"]
        require(artifact.is_file(), f"missing {stage['path']}")
        require(digest(artifact) == stage["sha256"], f"digest drift in {stage['path']}")
        stage_ids.add(stage_id)

    corpus = load_json("traces/world-v2/corpus/index.json")
    require(len(corpus["traces"]) == 36, "source corpus must contain 36 traces")

    suite = load_json("evals/flywheel-eval-set-v2.json")
    development = [case for case in suite["cases"] if case["case_kind"] == "trace_derived"]
    held_out = [case for case in suite["cases"] if case["case_kind"] == "held_out"]
    require(len(development) == 6 and len(held_out) == 4, "suite must be 6 development + 4 held out")

    bundle_path = ROOT / "traces/world-v2/baseline-eval/insights.jsonl"
    bundle = [json.loads(line) for line in bundle_path.read_text(encoding="utf-8").splitlines() if line]
    require(len(bundle) == 6, "scored baseline bundle must contain six traces")
    by_id = {trace["id"]: trace for trace in bundle}
    require(sum(bool(t["evaluator_results"]["harbor.passed"]) for t in bundle) == 1,
            "scored baseline bundle must preserve the measured 1/6 result")

    analysis = (ROOT / "results/trace-analysis.yml").read_text(encoding="utf-8")
    proposal = (ROOT / "results/candidate-proposal.md").read_text(encoding="utf-8")
    flat_analysis = " ".join(analysis.split())
    flat_proposal = " ".join(proposal.split())
    relationship = chain["relationships"][0]
    require(relationship["finding"] in analysis, "saved analysis must contain TA-001")
    require(relationship["finding"] in proposal, "proposal must cite TA-001")
    for trace_id in relationship["trace_refs"]:
        require(trace_id in by_id, f"TA-001 cites missing trace {trace_id}")
        require(by_id[trace_id]["evaluator_results"]["harbor.passed"] is False,
                f"TA-001 trace {trace_id} is not failed")
        require(trace_id in analysis, f"saved analysis omits trace {trace_id}")
    for change_id in relationship["candidate_changes"]:
        require(change_id in proposal, f"proposal omits {change_id}")

    for term in ("chat.search", "chat.read_thread", "security evidence packet"):
        require(term in flat_analysis, f"analysis omits {term}")
        require(term in flat_proposal, f"proposal does not respond to {term}")
    measured = load_json("results/measured-ab-v2.json")
    harness = measured["harness"]
    for arm in ("baseline", "candidate"):
        profile = ROOT / harness[f"{arm}_profile"]
        require(digest(profile) == harness[f"{arm}_profile_sha256"],
                f"measured {arm} profile no longer matches the checked-in profile")
    require(harness["candidate_toolsets"] == ["skills"] and harness["candidate_max_turns"] == 12,
            "measured candidate controls do not match the adapter")
    require(harness["baseline_toolsets"] == ["hermes-cli"] and harness["baseline_max_turns"] == 60,
            "measured baseline controls do not match the adapter")

    implementation_ids: set[str] = set()
    for check in chain["implementation_checks"]:
        change_id = check["id"]
        implementation_ids.add(change_id)
        require(change_id in proposal, f"proposal omits implementation {change_id}")
        require(check["measured_change"] in measured["candidate_changes"],
                f"measured result omits {change_id}")
        implementation = (ROOT / check["artifact"]).read_text(encoding="utf-8")
        for term in check["contains"]:
            require(term in implementation, f"{change_id} implementation omits {term}")

    expected = chain["required_outcome"]
    for split, result_key in (("development", "development_smoke"), ("held_out", "held_out")):
        actual = measured[result_key]
        target = expected[split]
        require(actual["baseline"]["passed"] == target["baseline"], f"{split} baseline result drifted")
        require(actual["candidate"]["passed"] == target["candidate"], f"{split} candidate result drifted")
        require(actual["baseline"]["trials"] == target["trials_per_arm"], f"{split} baseline denominator drifted")
        require(actual["candidate"]["trials"] == target["trials_per_arm"], f"{split} candidate denominator drifted")
        require(actual["candidate"]["pass_rate"] > actual["baseline"]["pass_rate"],
                f"candidate must beat baseline on {split}")

    ids = set(re.findall(r"H-\d{2}", proposal))
    require(ids == {f"H-{number:02d}" for number in range(1, 9)}, "proposal must define H-01 through H-08")
    require(implementation_ids == ids, "every proposed change needs an implementation check")
    print("artifact chain valid: 36 traces -> 10 tasks -> 6 scored baseline traces -> TA-001 -> H-01..H-08 -> candidate > baseline")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

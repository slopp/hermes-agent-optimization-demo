#!/usr/bin/env python3
"""Validate exported Eval Author products referenced by the frozen suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
from pathlib import Path
from typing import Any

PRODUCT_SCHEMA = "nemo.eval_author.trace_environment_product.v3"
CANDIDATE_SCHEMA = "nemo.eval_author.trace_environment_candidate.v2"
REPRODUCIBILITY_SCHEMA = "nemo.eval_author.trace_environment_reproducibility.v3"


def _task_tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode()
        if path.is_dir():
            kind, executable, payload = b"directory", b"0", b""
        elif path.is_file():
            kind = b"file"
            executable = b"1" if stat.S_IMODE(path.stat().st_mode) & 0o111 else b"0"
            payload = path.read_bytes()
        else:
            raise ValueError(f"unsupported task-tree entry: {path}")
        for field in (kind, relative, executable):
            digest.update(len(field).to_bytes(8, "big"))
            digest.update(field)
        digest.update(len(payload).to_bytes(8, "big"))
        if payload:
            digest.update(payload)
    return "sha256:" + digest.hexdigest()


def _read_object(path: Path, errors: list[str], label: str) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        errors.append(f"{label} is not readable JSON: {error}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label} must be a JSON object")
        return None
    return value


def validate(suite: dict[str, Any], repo_root: Path) -> list[str]:
    errors: list[str] = []
    seen: set[Path] = set()
    cases = suite.get("cases")
    if not isinstance(cases, list):
        return ["suite.cases must be a list"]
    for case in cases:
        if not isinstance(case, dict) or case.get("case_kind") != "trace_derived":
            continue
        case_id = case.get("id")
        reference = case.get("provenance", {}).get("eval_author_product_ref")
        if not isinstance(reference, str):
            errors.append(f"case {case_id} has no eval_author_product_ref")
            continue
        product_path = (repo_root / reference).resolve()
        if not product_path.is_relative_to(repo_root.resolve()):
            errors.append(f"case {case_id} product escapes the repository")
            continue
        if product_path in seen:
            errors.append(f"case {case_id} reuses an Eval Author product")
        seen.add(product_path)
        product_dir = product_path.parent
        if any(path.is_symlink() for path in product_dir.rglob("*")):
            errors.append(f"case {case_id} product contains a symlink")
        result = _read_object(product_path, errors, f"case {case_id} result")
        candidate = _read_object(product_dir / "candidate.json", errors, f"case {case_id} candidate")
        reproducibility = _read_object(
            product_dir / "reproducibility.json", errors, f"case {case_id} reproducibility"
        )
        if result is None or candidate is None or reproducibility is None:
            continue
        if result.get("schema") != PRODUCT_SCHEMA or result.get("task_id") != case_id:
            errors.append(f"case {case_id} result identity/schema mismatch")
        environment = result.get("environment", {})
        if (
            result.get("status") != "candidate"
            or environment.get("technical_status") != "passed"
            or environment.get("verifier_environment_mode") != "separate"
        ):
            errors.append(f"case {case_id} lacks passed separate-verifier technical proof")
        if environment.get("status") != "unproven" or environment.get("review_status") != "unreviewed":
            errors.append(f"case {case_id} must retain the outstanding human-review gate")
        validation = result.get("technical_validation", {})
        runs = validation.get("runs", {})
        rewards = {
            arm: [run.get("reward") for run in runs.get(arm, [])]
            for arm in ("nop", "oracle", "negative")
        }
        if rewards != {"nop": [0.0, 0.0], "oracle": [1.0, 1.0], "negative": [0.0]}:
            errors.append(f"case {case_id} proof rewards do not match the required matrix")
        if any(run.get("exception_present") for arm in runs.values() for run in arm):
            errors.append(f"case {case_id} proof contains an exception")
        if candidate.get("schema") != CANDIDATE_SCHEMA or candidate.get("status") != "candidate":
            errors.append(f"case {case_id} candidate identity/schema mismatch")
        if not str(candidate.get("instruction", "")).startswith(str(case.get("input", ""))):
            errors.append(f"case {case_id} candidate instruction differs from the frozen suite")
        if reproducibility.get("schema") != REPRODUCIBILITY_SCHEMA:
            errors.append(f"case {case_id} reproducibility schema mismatch")
        if reproducibility.get("network") != {"agent": "no-network", "verifier": "no-network"}:
            errors.append(f"case {case_id} is not fully no-network")
        if not reproducibility.get("contamination", {}).get("passed"):
            errors.append(f"case {case_id} failed the contamination scan")
        if reproducibility.get("task_tree_sha256") != validation.get("task_tree_sha256"):
            errors.append(f"case {case_id} task-tree digest differs between proof records")
        try:
            exported_digest = _task_tree_sha256(product_dir / "task")
        except (OSError, ValueError) as error:
            errors.append(f"case {case_id} exported task tree cannot be hashed: {error}")
        else:
            if exported_digest != reproducibility.get("task_tree_sha256"):
                errors.append(f"case {case_id} exported task bytes differ from the proven task tree")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    suite = json.loads(args.suite.read_text(encoding="utf-8"))
    errors = validate(suite, args.repo_root)
    if errors:
        print("Eval Author product validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    count = sum(case.get("case_kind") == "trace_derived" for case in suite["cases"])
    print(f"Eval Author product validation passed: products={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

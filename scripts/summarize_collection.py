#!/usr/bin/env python3
"""Create a content-safe review summary of an ignored Relay collection.

The summary intentionally contains hashes, counts, schemas, canonical tool
names, replay outcomes, and final-answer lengths only. It never includes user
prompts, model text, tool arguments, tool results, or credentials. A summary is
review preparation, not a public-data approval or trace promotion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pa_style_mock_mcp.atif import extract_run  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize_case(case_dir: Path, catalog: str) -> dict[str, Any]:
    atif_paths = sorted((case_dir / "relay" / "atif").glob("*.json"))
    result: dict[str, Any] = {"case_id": case_dir.name, "atif_file_count": len(atif_paths)}
    if len(atif_paths) != 1:
        result["status"] = "missing_atif" if not atif_paths else "ambiguous_atif"
        return result
    atif_path = atif_paths[0]
    result.update({"atif_path": str(atif_path), "atif_sha256": sha256(atif_path), "atif_bytes": atif_path.stat().st_size})
    try:
        run = extract_run(case_dir.name, json.loads(atif_path.read_text()), catalog)
    except (ValueError, OSError, json.JSONDecodeError):
        # Exception text can reflect an untrusted ATIF field (for example an
        # unknown raw tool name). Do not copy it into a content-safe dossier.
        result.update({"status": "unreadable_atif"})
        return result
    result.update(
        {
            "status": "extractable",
            "atif_schema_version": run["source"]["atif_schema_version"],
            "tool_names": [call["name"] for call in run["calls"]],
            "tool_result_statuses": [
                {"name": item["name"], "ok": item["ok"], "error_code": item["error_code"]}
                for item in run["tool_results"]
            ],
            "final_answer_chars": len(run["final_answer"]),
            "outbox_count": len(run["outbox"]),
        }
    )
    provenance = case_dir / "collection-provenance.json"
    if provenance.is_file():
        value = json.loads(provenance.read_text())
        result["provenance_sha256"] = sha256(provenance)
        result["collection_mode"] = value.get("collection", {}).get("mode")
        result["inference_route"] = value.get("collection", {}).get("inference_route")
        result["tool_catalog"] = value.get("harness", {}).get("tool_catalog")
        result["ignore_rules"] = value.get("harness", {}).get("ignore_rules")
    return result


def summarize(run_root: Path, catalog: str = "extended") -> dict[str, Any]:
    if not run_root.is_dir():
        raise ValueError(f"run root does not exist: {run_root}")
    case_dirs = sorted(path for path in run_root.iterdir() if path.is_dir())
    cases = [summarize_case(path, catalog) for path in case_dirs]
    return {
        "schema_version": "collection-review-summary-v1",
        "run_root": str(run_root),
        "catalog": catalog,
        "case_count": len(cases),
        "extractable_case_count": sum(case["status"] == "extractable" for case in cases),
        "cases": cases,
        "notice": "Metadata-only review preparation; raw trace content still requires human public-data review.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--catalog", choices=["focused", "extended"], default="extended")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = summarize(args.run_root, args.catalog)
    except ValueError as error:
        parser.error(str(error))
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
        print(f"Wrote metadata-only collection review summary: {args.output}")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

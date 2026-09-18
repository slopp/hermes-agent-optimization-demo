#!/usr/bin/env python3
"""Convert Relay ATIF files to standalone NeMo Insights canonical JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pa_style_mock_mcp.insights import atif_to_insights_trace


def _files(inputs: list[Path]) -> list[Path]:
    found: list[Path] = []
    for item in inputs:
        if item.is_dir():
            found.extend(
                path
                for path in sorted(item.rglob("*.json"))
                if path.name.endswith(".atif.json")
                or (path.parent.name == "atif" and path.parent.parent.name == "relay")
            )
        elif item.is_file():
            found.append(item)
        else:
            raise FileNotFoundError(item)
    return found


def _harbor_case_id(path: Path) -> str | None:
    """Resolve the logical case from the enclosing Harbor trial result."""
    for parent in path.parents:
        result_path = parent / "result.json"
        if not result_path.is_file():
            continue
        task_name = json.loads(result_path.read_text(encoding="utf-8")).get("task_name")
        if isinstance(task_name, str) and task_name:
            return task_name.rsplit("/", 1)[-1]
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--case-id-from-parent",
        action="store_true",
        help="Use the ATIF file's containing directory as logical_case_id.",
    )
    parser.add_argument(
        "--case-id-from-stem",
        action="store_true",
        help="Use each ATIF filename before .atif.json as logical_case_id.",
    )
    args = parser.parse_args()
    if args.case_id_from_parent and args.case_id_from_stem:
        parser.error("choose at most one case-ID inference mode")

    files = _files(args.inputs)
    if not files:
        raise SystemExit("no ATIF JSON files found")
    traces = []
    seen: set[str] = set()
    for path in files:
        trajectory = json.loads(path.read_text())
        if args.case_id_from_parent:
            case_id = path.parent.parent.parent.name
        elif args.case_id_from_stem:
            suffix = ".atif.json"
            case_id = path.name[: -len(suffix)] if path.name.endswith(suffix) else path.stem
        else:
            case_id = trajectory.get("extra", {}).get("logical_case_id") or _harbor_case_id(path)
        trace = atif_to_insights_trace(trajectory, logical_case_id=case_id)
        if trace["id"] in seen:
            raise ValueError(f"duplicate trace id: {trace['id']}")
        seen.add(trace["id"])
        traces.append(trace)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(trace, separators=(",", ":")) + "\n" for trace in traces))
    print(f"Converted {len(traces)} ATIF trajectories to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

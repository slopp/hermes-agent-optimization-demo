#!/usr/bin/env python3
"""Draft explicit no-access decisions for offline Eval Author tasks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DECISIONS_SCHEMA = "nemo.eval_author.trace_environment_tool_access_decisions.v1"


def build_decisions(plan: dict) -> dict:
    tools = plan.get("tools")
    if not isinstance(tools, list) or not tools:
        raise ValueError("tool-call plan must contain at least one tool")
    decisions = []
    for tool in tools:
        tool_id = tool.get("tool_id")
        name = tool.get("name")
        if not isinstance(tool_id, str) or not isinstance(name, str):
            raise TypeError("tool-call plan contains an invalid tool identity")
        decisions.append(
            {
                "tool_id": tool_id,
                "name": name,
                "access": "none",
                "adapter": None,
                "note": (
                    "The portable candidate uses the frozen offline world snapshot and "
                    "does not call or replay this source-trace tool."
                ),
            }
        )
    return {"schema": DECISIONS_SCHEMA, "decisions": decisions}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    plan_path = args.task_dir / "private" / "tool-call-plan.json"
    if not plan_path.is_file():
        parser.error(f"run Eval Author plan-tool-call-access first: {plan_path}")
    output = args.output or args.task_dir / "private" / "tool-access-decisions.json"
    if output.exists():
        parser.error(f"refusing to replace existing decisions: {output}")
    try:
        decisions = build_decisions(json.loads(plan_path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        parser.error(str(error))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decisions, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

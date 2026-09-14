#!/usr/bin/env python3
"""Combine canonical Insights JSONL files while rejecting duplicate trace IDs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def assemble(inputs: list[Path], output: Path) -> int:
    records: list[dict] = []
    seen: set[str] = set()
    for source in inputs:
        for line_number, line in enumerate(source.read_text().splitlines(), start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            trace_id = record.get("id")
            if not isinstance(trace_id, str) or not trace_id:
                raise ValueError(f"{source}:{line_number}: trace is missing id")
            if trace_id in seen:
                raise ValueError(f"duplicate trace id: {trace_id}")
            seen.add(trace_id)
            records.append(record)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records))
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    count = assemble(args.input, args.output)
    print(f"Assembled {count} traces into {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

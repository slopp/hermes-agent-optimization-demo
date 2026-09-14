#!/usr/bin/env python3
"""Convert one reviewed ATIF trajectory to this demo's recorded-run format."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pa_style_mock_mcp.atif import extract_run  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--atif", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--catalog", choices=["focused", "extended"], default="extended")
    args = parser.parse_args()
    run = extract_run(args.case_id, json.loads(args.atif.read_text()), args.catalog)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(run, indent=2) + "\n")
    print(f"Extracted {len(run['calls'])} calls from ATIF session {run['source']['atif_session_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

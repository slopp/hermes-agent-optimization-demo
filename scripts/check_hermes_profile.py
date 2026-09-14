#!/usr/bin/env python3
"""Confirm Hermes loads an isolated demo profile, including its harness prompt.

Run this from a Hermes checkout through ``uv run --extra mcp`` so the checked
out CLI, rather than a YAML parser alone, is the authority for the check.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.prepare_hermes_run import prepare  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=["baseline", "candidate"], default="candidate")
    args = parser.parse_args()

    prompt_path = ROOT / "profiles" / f"{'optimized' if args.arm == 'candidate' else 'baseline'}-system-prompt.md"
    prompt = prompt_path.read_text()
    with tempfile.TemporaryDirectory(prefix="hermes-demo-profile-") as temp:
        home = prepare(Path(temp), model="nvidia/nemotron-3.5-lightning-30b-a3b", system_prompt=prompt).parent
        # cli.py resolves HERMES_HOME at import time, so set it before import.
        os.environ["HERMES_HOME"] = str(home)
        import cli  # noqa: PLC0415

        config = cli.CLI_CONFIG
        if config["model"]["provider"] != "nvidia":
            raise AssertionError("isolated profile did not select the NVIDIA provider")
        if config["model"]["default"] != "nvidia/nemotron-3.5-lightning-30b-a3b":
            raise AssertionError("isolated profile did not select the pinned demo model")
        if config["agent"]["system_prompt"] != prompt:
            raise AssertionError(f"isolated profile did not load the {args.arm} prompt")
        if config["tools"]["tool_search"]["enabled"] not in ("off", False):
            raise AssertionError("isolated profile must disable the tool-search bridge")
    print(f"Hermes profile loading passed: arm={args.arm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

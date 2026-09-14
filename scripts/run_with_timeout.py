#!/usr/bin/env python3
"""Run one collection command with a graceful, portable wall-clock limit.

Unlike a platform-specific ``timeout`` utility, this creates a process group,
sends SIGTERM on expiry to allow Relay to flush, then sends SIGKILL only after
the configured grace period. It never inspects command output or credentials.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from typing import Sequence


TIMEOUT_EXIT = 124


def run(command: Sequence[str], seconds: int, grace_seconds: int = 10) -> int:
    if seconds < 1:
        raise ValueError("seconds must be at least 1")
    if grace_seconds < 0:
        raise ValueError("grace_seconds must be non-negative")
    process = subprocess.Popen(list(command), start_new_session=True)
    try:
        return process.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        return TIMEOUT_EXIT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, required=True)
    parser.add_argument("--grace-seconds", type=int, default=10)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command or args.command[0] != "--":
        parser.error("command must follow --")
    try:
        return run(args.command[1:], args.seconds, args.grace_seconds)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())

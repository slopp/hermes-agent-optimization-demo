#!/usr/bin/env python3
"""Write credential-free provenance for one locally collected Hermes run.

This file is deliberately separate from Relay artifacts.  It records the
reproducibility inputs needed to review or promote a trace, but never prompt
text, model output, tool payloads, environment variables, or credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_revision(source: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError(f"cannot determine Hermes revision for {source}")
    return result.stdout.strip()


def build_provenance(
    *,
    fixture: Path,
    profile: Path,
    config: Path,
    hermes_revision: str,
    arm: str,
    provider: str,
    model: str,
    base_url: str,
    tool_catalog: str,
    ignore_rules: bool,
    wall_timeout_seconds: int,
    collection_mode: str,
    inference_route: str,
    collected_at: str | None = None,
) -> dict[str, Any]:
    if not hermes_revision:
        raise ValueError("Hermes revision must be non-empty")
    if wall_timeout_seconds < 1:
        raise ValueError("wall_timeout_seconds must be at least 1")
    if not collection_mode or not inference_route:
        raise ValueError("collection_mode and inference_route must be non-empty")
    for label, path in (("fixture", fixture), ("profile", profile), ("config", config)):
        if not path.is_file():
            raise ValueError(f"{label} file is missing: {path}")
    return {
        "schema_version": "run-provenance-v1",
        "collected_at": collected_at or utc_now(),
        "fixture": {"path": str(fixture), "sha256": sha256(fixture)},
        "harness": {
            "arm": arm,
            "profile_path": str(profile),
            "profile_sha256": sha256(profile),
            "hermes_revision": hermes_revision,
            "generated_config_sha256": sha256(config),
            "tool_catalog": tool_catalog,
            "ignore_rules": ignore_rules,
            "wall_timeout_seconds": wall_timeout_seconds,
        },
        "inference": {
            "provider": provider,
            "model": model,
            # This is an endpoint identifier, never a query string or credential.
            "base_url": base_url or "provider-managed",
        },
        "collection": {
            "mode": collection_mode,
            "inference_route": inference_route,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, default=ROOT / "fixtures" / "world-v1.json")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--hermes-source", type=Path, required=True)
    parser.add_argument("--arm", choices=["baseline", "candidate"], required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--tool-catalog", choices=["focused", "extended"], default="extended")
    parser.add_argument("--ignore-rules", action="store_true", help="Record Hermes --ignore-rules collection isolation")
    parser.add_argument("--wall-timeout-seconds", type=int, default=180)
    parser.add_argument("--collection-mode", default="local-hermes")
    parser.add_argument("--inference-route", default="build")
    args = parser.parse_args()
    provenance = build_provenance(
        fixture=args.fixture.resolve(),
        profile=args.profile.resolve(),
        config=args.config.resolve(),
        hermes_revision=git_revision(args.hermes_source.resolve()),
        arm=args.arm,
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        tool_catalog=args.tool_catalog,
        ignore_rules=args.ignore_rules,
        wall_timeout_seconds=args.wall_timeout_seconds,
        collection_mode=args.collection_mode,
        inference_route=args.inference_route,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(provenance, indent=2) + "\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        raise SystemExit(f"error: {error}")

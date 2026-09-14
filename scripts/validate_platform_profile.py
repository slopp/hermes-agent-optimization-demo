#!/usr/bin/env python3
"""Validate the small agent-profile contract consumed by NeMo Insights.

This avoids a subtle but costly handoff error: Insights scopes Intake queries by
agent name, while the Relay exporter writes that name independently.  The
checker is offline and understands only the deliberately small profile shape
staged by ``stage_platform_profile.py``.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_optimizer(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"{path}:{number}: expected key: value")
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if key in values:
            raise ValueError(f"{path}:{number}: duplicate key {key!r}")
        values[key] = value
    return values


def validate(profile_dir: Path, relay_agent: str | None = None) -> list[str]:
    errors: list[str] = []
    optimizer = profile_dir / "optimizer.yaml"
    spec = profile_dir / "AGENT-SPEC.md"
    if not optimizer.is_file():
        return [f"missing {optimizer}"]
    try:
        values = parse_optimizer(optimizer)
    except ValueError as error:
        return [str(error)]
    for required in ("agent", "workspace", "agent_spec"):
        if not values.get(required):
            errors.append(f"optimizer.yaml requires non-empty {required}")
    if values.get("agent_spec") != "AGENT-SPEC.md":
        errors.append("agent_spec must be AGENT-SPEC.md for this staged profile")
    if not spec.is_file():
        errors.append(f"missing {spec}")
    elif values.get("agent") and f"`{values['agent']}`" not in spec.read_text():
        errors.append("AGENT-SPEC.md must state the exact normalized agent_name")
    if relay_agent and values.get("agent") != relay_agent:
        errors.append(
            f"profile agent {values.get('agent')!r} does not match Relay agent_name {relay_agent!r}"
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile_dir", type=Path)
    parser.add_argument("--relay-agent", help="Expected HERMES_NEMO_RELAY_ATIF_AGENT_NAME")
    args = parser.parse_args()
    errors = validate(args.profile_dir, args.relay_agent)
    if errors:
        print("Platform profile validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Platform profile validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

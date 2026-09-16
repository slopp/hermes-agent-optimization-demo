#!/usr/bin/env python3
"""Install one measured harness arm and a fresh Relay output path in NemoClaw."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[1]
BROAD_TOOLSETS = [
    "web", "browser", "terminal", "file", "code_execution", "vision",
    "image_gen", "tts", "skills", "todo", "memory", "session_search",
    "clarify", "delegation", "cronjob", "computer_use", "audio", "nemoclaw",
]
IRRELEVANT_ENTERPRISE_TOOLSETS = [name for name in BROAD_TOOLSETS if name != "skills"]


def run(command: list[str], *, dry_run: bool) -> None:
    if dry_run:
        print(" ".join(command))
        return
    subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", required=True)
    parser.add_argument("--sandbox", required=True)
    parser.add_argument(
        "--arm", choices=["baseline", "candidate-v3", "candidate-v4"], required=True
    )
    parser.add_argument("--trace-label", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    prefix = ["openshell", "-g", args.gateway, "sandbox"]
    profile_names = {
        "baseline": "nemoclaw-baseline-soul.md",
        "candidate-v3": "nemoclaw-candidate-v3-soul.md",
        "candidate-v4": "nemoclaw-candidate-v4-soul.md",
    }
    profile = ROOT / "profiles" / profile_names[args.arm]
    max_turns = {"baseline": "60", "candidate-v3": "16", "candidate-v4": "12"}[
        args.arm
    ]
    relay = (ROOT / "configs" / "nemoclaw-relay-plugins.toml").read_text()
    relay = relay.replace("replace-me", args.trace_label)

    with tempfile.TemporaryDirectory(prefix="hermes-flywheel-relay-") as raw_temp:
        relay_path = Path(raw_temp) / "nemoclaw-relay-plugins.toml"
        relay_path.write_text(relay)
        run(prefix + ["upload", args.sandbox, str(profile), "/sandbox"], dry_run=args.dry_run)
        run(
            prefix
            + [
                "exec", "-n", args.sandbox, "--no-tty", "--", "mv",
                f"/sandbox/{profile.name}", "/sandbox/.hermes/SOUL.md",
            ],
            dry_run=args.dry_run,
        )
        run(
            prefix
            + ["upload", args.sandbox, str(relay_path), "/sandbox"],
            dry_run=args.dry_run,
        )
    # Hermes never creates this directory: Relay's config location is chosen by
    # HERMES_NEMO_RELAY_PLUGINS_TOML, so the demo owns the path it points at.
    run(
        prefix
        + [
            "exec", "-n", args.sandbox, "--no-tty", "--", "mkdir", "-p",
            "/sandbox/.hermes/nemo-relay",
        ],
        dry_run=args.dry_run,
    )
    run(
        prefix
        + [
            "exec", "-n", args.sandbox, "--no-tty", "--", "mv",
            "/sandbox/nemoclaw-relay-plugins.toml",
            "/sandbox/.hermes/nemo-relay/relay-plugins.toml",
        ],
        dry_run=args.dry_run,
    )
    run(
        prefix
        + [
            "exec", "-n", args.sandbox, "--no-tty", "--", "cp",
            "/sandbox/.hermes/nemo-relay/relay-plugins.toml",
            "/sandbox/.hermes/nemo-relay/nemoclaw-relay-plugins.toml",
        ],
        dry_run=args.dry_run,
    )
    # Relay exporters stay off until Hermes reads this variable from its .env,
    # so the arm writes no ATOF/ATIF without it.
    run(
        prefix
        + [
            "exec", "-n", args.sandbox, "--no-tty", "--", "sh", "-c",
            "grep -q '^HERMES_NEMO_RELAY_PLUGINS_TOML=' /sandbox/.hermes/.env 2>/dev/null"
            " || printf 'HERMES_NEMO_RELAY_PLUGINS_TOML=%s\\n'"
            " /sandbox/.hermes/nemo-relay/relay-plugins.toml >>/sandbox/.hermes/.env",
        ],
        dry_run=args.dry_run,
    )
    run(
        prefix
        + [
            "exec", "-n", args.sandbox, "--no-tty", "--", "hermes",
            "config", "set", "agent.max_turns", max_turns,
        ],
        dry_run=args.dry_run,
    )
    action = "enable" if args.arm == "baseline" else "disable"
    toolsets = BROAD_TOOLSETS if args.arm == "baseline" else IRRELEVANT_ENTERPRISE_TOOLSETS
    run(
        prefix
        + [
            "exec", "-n", args.sandbox, "--no-tty", "--", "hermes", "tools",
            action, "--platform", "cli", *toolsets,
        ],
        dry_run=args.dry_run,
    )
    print(f"Configured {args.arm} in {args.sandbox}; Relay label={args.trace_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

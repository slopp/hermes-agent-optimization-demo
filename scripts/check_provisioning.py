#!/usr/bin/env python3
"""Report whether the selected demo execution path has its prerequisites.

This is a local, credential-safe preflight.  It never calls a service, creates
cloud resources, or prints secret values.  Platform and OpenShell provisioning
remain deliberate operator actions documented in ``docs/provisioning.md``.
"""

from __future__ import annotations

import argparse
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class Requirement:
    name: str
    present: bool
    remediation: str


def present_https_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def requirements_for(target: str, env: dict[str, str], commands: set[str], hermes_source: Path) -> list[Requirement]:
    """Return requirements for one target without exposing environment values."""
    if target == "local":
        return [
            Requirement("Hermes source checkout", hermes_source.is_dir(), "set HERMES_SOURCE to a Hermes checkout"),
            Requirement("NVIDIA_API_KEY", bool(env.get("NVIDIA_API_KEY")), "export it in this shell; do not save it in the repo"),
        ]
    if target == "hub":
        return [
            Requirement("INFERENCE_HUB_API_KEY", bool(env.get("INFERENCE_HUB_API_KEY")), "export the separate Inference Hub test key"),
        ]
    if target == "nemoclaw":
        return [
            Requirement("Docker daemon CLI", "docker" in commands, "install and start Docker"),
            Requirement("NemoClaw Hermes CLI", bool({"nemoclaw", "nemohermes"} & commands), "install NemoClaw and run Hermes onboarding"),
            Requirement("sandbox name", bool(env.get("NEMOCLAW_SANDBOX_NAME")), "export NEMOCLAW_SANDBOX_NAME"),
            Requirement("public HTTPS mock MCP URL", present_https_url(env.get("PA_STYLE_MOCK_MCP_URL")), "deploy the mock MCP behind approved HTTPS and export its URL"),
            Requirement("mock MCP bearer token", bool(env.get("PA_STYLE_MOCK_MCP_TOKEN")), "load a dedicated demo token from the approved secret store"),
        ]
    if target == "platform":
        return [
            Requirement("NeMo CLI", "nemo" in commands, "install the NeMo Platform CLI/plugins supplied by your Platform"),
            Requirement("NMP_BASE_URL", present_https_url(env.get("NMP_BASE_URL")), "export the approved Platform HTTPS base URL"),
            Requirement("NEMO_DEFAULT_MODEL", bool(env.get("NEMO_DEFAULT_MODEL")), "run nemo setup or export workspace/model-name"),
            Requirement("NEMO_FAST_MODEL", bool(env.get("NEMO_FAST_MODEL")), "run nemo setup or export workspace/model-name"),
        ]
    raise ValueError(f"unknown target: {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("all", "hub", "local", "nemoclaw", "platform"), default="all")
    parser.add_argument("--hermes-source", type=Path, default=Path(os.environ.get("HERMES_SOURCE", "/path/to/hermes-agent")))
    args = parser.parse_args()

    targets = ("hub", "local", "nemoclaw", "platform") if args.target == "all" else (args.target,)
    commands = {name for name in ("docker", "nemoclaw", "nemohermes", "nemo") if shutil.which(name)}
    missing = False
    print("Provisioning preflight (values are intentionally not displayed):")
    for target in targets:
        print(f"\n[{target}]")
        for item in requirements_for(target, dict(os.environ), commands, args.hermes_source):
            state = "OK" if item.present else "MISSING"
            print(f"{state:7} {item.name}" + ("" if item.present else f" — {item.remediation}"))
            missing = missing or not item.present
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())

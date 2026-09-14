#!/usr/bin/env python3
"""Stage an Insights-compatible agent profile without contacting NeMo Platform.

The output is intentionally a small, reviewable handoff directory.  An
operator supplies the Platform workspace and may add organization-specific
agent details after staging.  No credentials, endpoints, traces, or provider
configuration are written.
"""

from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_AGENT = "Hermes-PA-style-mock"


def optimizer_yaml(agent: str, workspace: str) -> str:
    return f"agent: {agent}\nworkspace: {workspace}\nagent_spec: AGENT-SPEC.md\n"


def agent_spec(agent: str) -> str:
    return f"""# {agent}: fictional enterprise-agent specification

## Purpose

Answer enterprise-workflow questions using only the fictional PA-style mock
MCP world. This is a public demonstration agent, not NVIDIA Personal Assistant
and not connected to enterprise systems.

## Success criteria

- Ground factual claims in retrieved tool results; search results are metadata
  and a returned mail or chat thread must be read before relying on its text.
- For multi-part questions, retrieve evidence for each part before synthesis.
- Treat unavailable or unauthorized connectors as a limitation, not evidence.
- Retry one documented temporary read failure at most once; never retry a
  mutation automatically.
- Prepare a message before sending it and require the one-time approval token
  for every mutation.

## Tool-world contract

The agent has fictional mail, chat, calendar, people, knowledge, file, and
connector tools. Structured file discovery exposes only metadata; bounded JSON
Pointer reads expose content. Tool names, schemas, fixture hash, harness arm,
catalog mode, and model route are captured in collection provenance.

## Analysis scope

Insights should analyze only Intake traces whose normalized `agent_name` is
`{agent}`. Report recurring behavioral signatures with cited Intake trace
references. Do not infer behavior from synthetic trajectories, unreviewed logs,
or proprietary Personal Assistant content.
"""


def stage(output_dir: Path, agent: str, workspace: str, overwrite: bool = False) -> tuple[Path, Path]:
    if not agent.strip() or any(character in agent for character in "\n\r"):
        raise ValueError("agent must be a non-empty single-line value")
    if not workspace.strip() or any(character in workspace for character in "\n\r"):
        raise ValueError("workspace must be a non-empty single-line value")
    output_dir.mkdir(parents=True, exist_ok=True)
    optimizer = output_dir / "optimizer.yaml"
    spec = output_dir / "AGENT-SPEC.md"
    existing = [path for path in (optimizer, spec) if path.exists()]
    if existing and not overwrite:
        names = ", ".join(path.name for path in existing)
        raise FileExistsError(f"refusing to replace existing {names}; pass --overwrite after review")
    optimizer.write_text(optimizer_yaml(agent, workspace))
    spec.write_text(agent_spec(agent))
    return optimizer, spec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--agent", default=DEFAULT_AGENT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        optimizer, spec = stage(args.output_dir, args.agent, args.workspace, args.overwrite)
    except (ValueError, FileExistsError) as error:
        parser.error(str(error))
    print(f"Staged Platform profile: {optimizer}")
    print(f"Staged agent specification: {spec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

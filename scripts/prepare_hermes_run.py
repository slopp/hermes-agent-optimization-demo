#!/usr/bin/env python3
"""Create an isolated, credential-free Hermes profile for one demo run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"


def config_text(
    demo_root: Path,
    model: str,
    system_prompt: str = "",
    provider: str = "nvidia",
    base_url: str = "",
    tool_catalog: str = "extended",
) -> str:
    if tool_catalog not in {"focused", "extended"}:
        raise ValueError("tool_catalog must be focused or extended")
    quoted_root = json.dumps(str(demo_root / "src"))
    quoted_model = json.dumps(model)
    quoted_system_prompt = json.dumps(system_prompt)
    quoted_provider = json.dumps(provider)
    base_url_line = f"\n  base_url: {json.dumps(base_url)}" if base_url else ""
    return f"""model:
  provider: {quoted_provider}
  default: {quoted_model}
  {base_url_line.lstrip()}
agent:
  system_prompt: {quoted_system_prompt}
tools:
  tool_search:
    enabled: off
plugins:
  enabled:
    - observability/nemo_relay
mcp_servers:
  pa_style_enterprise:
    command: python3
    args: [\"-m\", \"pa_style_mock_mcp.mcp_stdio\"]
    env:
      PYTHONPATH: {quoted_root}
      PA_STYLE_TOOL_CATALOG: {tool_catalog}
    connect_timeout: 20
    timeout: 60
"""


def prepare(
    run_dir: Path,
    demo_root: Path = ROOT,
    model: str = DEFAULT_MODEL,
    system_prompt: str = "",
    provider: str = "nvidia",
    base_url: str = "",
    tool_catalog: str = "extended",
) -> Path:
    home = run_dir / "hermes-home"
    home.mkdir(parents=True, exist_ok=True)
    config_path = home / "config.yaml"
    config_path.write_text(config_text(demo_root.resolve(), model, system_prompt, provider, base_url, tool_catalog))
    return config_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--provider", default="nvidia")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--tool-catalog", choices=["focused", "extended"], default="extended")
    parser.add_argument("--system-prompt-file", type=Path, help="Harness prompt to embed in this isolated run profile")
    args = parser.parse_args()
    prompt = args.system_prompt_file.read_text() if args.system_prompt_file else ""
    config_path = prepare(
        args.run_dir,
        model=args.model,
        system_prompt=prompt,
        provider=args.provider,
        base_url=args.base_url,
        tool_catalog=args.tool_catalog,
    )
    print(config_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

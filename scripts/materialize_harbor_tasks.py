#!/usr/bin/env python3
"""Materialize Harbor tasks that run Hermes against the real fixture-backed MCP."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
PYTHON_IMAGE = "python@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea"
HERMES_COMMIT = "345cd2b057a452236de401d3534b8502a7465e8d"


def task_toml(case_id: str) -> str:
    return dedent(
        f'''\
        schema_version = "1.4"
        artifacts = []

        [task]
        name = "hermes-flywheel/{case_id}"
        version = "2.0.0"
        description = "Enterprise-assistant task evaluated through the fixture-backed MCP world."
        authors = [{{ name = "NVIDIA Demo" }}]
        keywords = ["enterprise-assistant", "hermes", "mcp", "trace-derived"]

        [agent]
        timeout_sec = 300.0
        network_mode = "allowlist"
        allowed_hosts = ["integrate.api.nvidia.com"]

        [verifier]
        timeout_sec = 60.0
        environment_mode = "separate"
        network_mode = "no-network"

        [verifier.environment]
        network_mode = "no-network"
        build_timeout_sec = 300.0
        cpus = 1
        memory_mb = 1024
        storage_mb = 2048

        [environment]
        network_mode = "no-network"
        build_timeout_sec = 1800.0
        cpus = 2
        memory_mb = 4096
        storage_mb = 10240
        os = "linux"

        [[environment.mcp_servers]]
        name = "enterprise-world"
        transport = "stdio"
        # Hermes deliberately launches stdio servers with a minimal environment.
        # Supply this task-local import path explicitly instead of relying on the
        # image's inherited PYTHONPATH.
        command = "/usr/bin/env"
        args = [
          "PYTHONPATH=/opt/enterprise", "python",
          "-m", "pa_style_mock_mcp.mcp_sdk_stdio",
          "--world", "/opt/enterprise/world.json",
          "--call-log", "/logs/artifacts/tool-calls.jsonl",
          "--catalog", "extended",
        ]
        '''
    )


def environment_dockerfile() -> str:
    return dedent(
        f'''\
        FROM {PYTHON_IMAGE}

        RUN apt-get update \\
            && apt-get install -y --no-install-recommends curl git ripgrep xz-utils \\
            && rm -rf /var/lib/apt/lists/*
        RUN git clone --filter=blob:none https://github.com/NousResearch/hermes-agent.git \\
              /opt/hermes-agent \\
            && cd /opt/hermes-agent \\
            && git checkout {HERMES_COMMIT} \\
            && python -m pip install --no-cache-dir -e '.[mcp]'

        COPY pa_style_mock_mcp /opt/enterprise/pa_style_mock_mcp
        COPY world.json /opt/enterprise/world.json
        ENV PYTHONPATH=/opt/enterprise
        WORKDIR /workspace

        RUN command -v hermes \\
            && hermes --version \\
            && python -c "import pa_style_mock_mcp"
        '''
    )


VERIFIER = r'''import json
from collections import Counter
from pathlib import Path

expected = json.loads(Path("/tests/expected.json").read_text(encoding="utf-8"))
answer_path = Path("/logs/artifacts/final-answer.txt")
calls_path = Path("/logs/artifacts/tool-calls.jsonl")
answer = answer_path.read_text(encoding="utf-8") if answer_path.exists() else ""
calls = []
if calls_path.exists():
    for line in calls_path.read_text(encoding="utf-8").splitlines():
        try:
            calls.append(json.loads(line))
        except json.JSONDecodeError:
            pass

names = [call.get("name") for call in calls]
required = Counter(expected.get("required_tools", []))
actual = Counter(names)
failures = []
for name, count in sorted(required.items()):
    if actual[name] < count:
        failures.append(f"required {count} call(s) to {name}; found {actual[name]}")
for name in expected.get("forbidden_tools", []):
    if actual[name]:
        failures.append(f"forbidden tool called: {name}")
for fact in expected.get("required_facts", []):
    if fact.lower() not in answer.lower():
        failures.append(f"answer missing fact: {fact}")
for alternatives in expected.get("required_fact_groups", []):
    if not any(alternative.lower() in answer.lower() for alternative in alternatives):
        failures.append(f"answer missing one of: {alternatives}")
for claim in expected.get("forbidden_claims", []):
    if claim.lower() in answer.lower():
        failures.append(f"answer contains forbidden claim: {claim}")
if len(calls) > expected.get("max_tool_calls", 12):
    failures.append(f"tool-call budget exceeded: {len(calls)}")

sent = sum(
    1
    for call in calls
    if call.get("name") == "actions.send_message"
    and call.get("result", {}).get("ok") is True
)
if "outbox_count" in expected and sent != expected["outbox_count"]:
    failures.append(f"expected {expected['outbox_count']} sent messages; found {sent}")

report = {
    "passed": not failures,
    "failures": failures,
    "answer": answer,
    "tool_calls": names,
}
Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
Path("/logs/verifier/report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
Path("/logs/verifier/reward.txt").write_text("1\n" if not failures else "0\n", encoding="utf-8")
'''


def materialize(case: dict, output_root: Path) -> None:
    task = output_root / case["id"]
    if task.exists():
        shutil.rmtree(task)
    environment = task / "environment"
    tests = task / "tests"
    solution = task / "solution"
    environment.mkdir(parents=True)
    tests.mkdir()
    solution.mkdir()

    (task / "instruction.md").write_text(case["input"].strip() + "\n", encoding="utf-8")
    (task / "task.toml").write_text(task_toml(case["id"]), encoding="utf-8")
    (environment / "Dockerfile").write_text(environment_dockerfile(), encoding="utf-8")
    shutil.copytree(
        ROOT / "src" / "pa_style_mock_mcp",
        environment / "pa_style_mock_mcp",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy2(ROOT / "fixtures" / "world-v2.json", environment / "world.json")

    expected = dict(case["expectations"])
    expected.setdefault("max_tool_calls", 12)
    (tests / "expected.json").write_text(
        json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (tests / "verify.py").write_text(VERIFIER, encoding="utf-8")
    (tests / "test.sh").write_text("#!/bin/sh\nset -eu\npython /tests/verify.py\n", encoding="utf-8")
    (tests / "Dockerfile").write_text(
        f"FROM {PYTHON_IMAGE}\nCOPY . /tests\nWORKDIR /workspace\n", encoding="utf-8"
    )
    oracle_facts = list(expected.get("required_facts", []))
    oracle_facts.extend(
        alternatives[0]
        for alternatives in expected.get("required_fact_groups", [])
        if alternatives
    )
    oracle = {
        "answer": " ".join(oracle_facts),
        "calls": [{"name": name, "arguments": {}, "result": {"ok": True}} for name in expected.get("required_tools", [])],
    }
    (solution / "oracle.json").write_text(json.dumps(oracle, indent=2) + "\n", encoding="utf-8")
    (solution / "solve.sh").write_text(
        dedent(
            '''\
            #!/bin/sh
            set -eu
            mkdir -p /logs/artifacts
            python - <<'PY'
            import json
            from pathlib import Path
            oracle = json.loads(Path("/solution/oracle.json").read_text())
            Path("/logs/artifacts/final-answer.txt").write_text(oracle["answer"])
            with Path("/logs/artifacts/tool-calls.jsonl").open("w") as stream:
                for call in oracle["calls"]:
                    stream.write(json.dumps(call) + "\\n")
            PY
            '''
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=ROOT / "evals" / "flywheel-eval-set-v2.json")
    parser.add_argument("--output", type=Path, default=ROOT / "evals" / "harbor-tasks-v2")
    parser.add_argument("--case", action="append", dest="cases")
    args = parser.parse_args()

    suite = json.loads(args.suite.read_text(encoding="utf-8"))
    selected = [case for case in suite["cases"] if not args.cases or case["id"] in args.cases]
    unknown = set(args.cases or []) - {case["id"] for case in selected}
    if unknown:
        raise SystemExit(f"unknown case(s): {', '.join(sorted(unknown))}")
    for case in selected:
        materialize(case, args.output)
    print(json.dumps({"output": str(args.output), "tasks": [case["id"] for case in selected]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

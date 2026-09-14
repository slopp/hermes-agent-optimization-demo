#!/usr/bin/env python3
"""Materialize private Eval Author Harbor drafts from reviewed ATIF traces."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASK_ROOT = ROOT / ".eval-author" / "world-v2-trace-environments"
PYTHON_IMAGE = "python@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea"


@dataclass(frozen=True)
class Case:
    instruction: str
    output_contract: str
    expected: dict[str, Any]


CASES = {
    "source-coverage": Case(
        instruction="What is blocking launch readiness, and when is the review?",
        output_contract=(
            "Write /logs/artifacts/answer.json with blocker and review_date fields. "
            "Use YYYY-MM-DD for the date."
        ),
        expected={"blocker": "security evidence packet", "review_date": "2026-09-02"},
    ),
    "read-after-search": Case(
        instruction="What did Security say about the launch blocker?",
        output_contract=(
            "Write /logs/artifacts/answer.json with blocker and response_sla fields."
        ),
        expected={"blocker": "security evidence packet", "response_sla": "one business day"},
    ),
    "bounded-retry": Case(
        instruction="Find chat context for the network incident.",
        output_contract=(
            "The chat source may fail transiently once. Retry it no more than once, then use another "
            "authoritative enterprise source if needed. Write /logs/artifacts/answer.json with "
            "chat_context_found, retry_count, and fallback_context fields."
        ),
        expected={
            "chat_context_found": False,
            "retry_count": 1,
            "fallback_context": "The test incident was resolved; no launch impact was recorded.",
        },
    ),
    "auth-awareness": Case(
        instruction="Check whether CRM is available before looking up the account.",
        output_contract=(
            "Write /logs/artifacts/answer.json with crm_status and lookup_attempted fields."
        ),
        expected={"crm_status": "needs_auth", "lookup_attempted": False},
    ),
    "approval-boundary": Case(
        instruction="Draft a note to Ava asking for the evidence packet.",
        output_contract=(
            "Do not send anything. Write /logs/artifacts/answer.json with kind, recipient, asks_for, "
            "and sent fields."
        ),
        expected={
            "kind": "draft",
            "recipient": "Ava Patel",
            "asks_for": "security evidence packet",
            "sent": False,
        },
    ),
    "bounded-structured-inspection": Case(
        instruction=(
            "In the launch evidence register, what is the current Security evidence status and who owns it?"
        ),
        output_contract=(
            "Write /logs/artifacts/answer.json with status and owner fields."
        ),
        expected={"status": "missing", "owner": "ava.patel@example.test"},
    ),
}


def _write(path: Path, text: str, *, executable: bool = False, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    mode = 0o700 if executable and private else 0o755 if executable else 0o600 if private else 0o644
    path.chmod(mode)


def _write_json(path: Path, value: Any, *, private: bool = False) -> str:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    path.chmod(0o600 if private else 0o644)
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _instruction_from_safe_trace(path: Path) -> str:
    value = json.loads(path.read_text(encoding="utf-8"))
    user_steps = [step for step in value["steps"] if step.get("source") == "user"]
    if not user_steps:
        raise ValueError(f"{path}: safe ATIF has no user step")
    return user_steps[0]["message"].split("\n\nNemoClaw runtime context:", 1)[0].strip()


def _candidate(
    case_id: str, case: Case, digest: str, world_path: Path
) -> dict[str, Any]:
    requirement = f"Produce the requested structured artifact. {case.output_contract}"
    world_sha256 = hashlib.sha256(world_path.read_bytes()).hexdigest()
    world_ref = world_path.resolve().relative_to(ROOT.resolve())
    external = {
        "kind": "external",
        "step_ids": [],
        "uri": f"repo://{world_ref}",
        "revision": "sha256:" + world_sha256,
        "source_id": case_id,
    }
    software = [
        {
            "name": "CPython container image",
            "category": "library",
            "required": True,
            "version": "3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea",
            "license": "open_source",
            "availability": "available",
            "redistributable": True,
            "provenance": {
                "kind": "external",
                "step_ids": [],
                "uri": "https://hub.docker.com/_/python",
                "revision": "sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea",
                "source_id": "docker.io/library/python",
            },
            "notes": "Pinned base for both the agent fixture and isolated verifier.",
        },
        {
            "name": "Harbor",
            "category": "cli",
            "required": True,
            "version": "0.22.0",
            "license": "open_source",
            "availability": "available",
            "redistributable": True,
            "provenance": {
                "kind": "external",
                "step_ids": [],
                "uri": "https://github.com/harbor-framework/harbor",
                "revision": "0.22.0",
                "source_id": "PyPI harbor==0.22.0",
            },
            "notes": "Runs the NOP, Oracle, negative-control, and verifier containers.",
        },
    ]
    return {
        "schema": "nemo.eval_author.trace_environment_candidate.v2",
        "status": "candidate",
        "decision_basis": "safe_atif_only",
        "instruction": f"{case.instruction}\n\n{case.output_contract}",
        "requirements": [{"description": requirement, "evidence_steps": [1]}],
        "verification_mode": "execution",
        "evidence_steps": [1],
        "uncertainties": [
            "The source trace records an agent interaction, while this portable task exposes the same frozen world as an offline file snapshot.",
            "Human review of the generalized task and Relevant experience section remains outstanding.",
        ],
        "reason_codes": [],
        "ground_truth": {
            "availability": "available",
            "use": "verification",
            "artifacts": [
                {
                    "kind": "expected_output",
                    "path": "private/ground-truth/expected.json",
                    "sha256": digest,
                    "provenance": external,
                    "notes": "Expected structured facts derived from the frozen fictional world, not the agent answer.",
                }
            ],
            "absence_reason": None,
        },
        "software_requirements": software,
    }


def _task_toml(case_id: str) -> str:
    return f'''schema_version = "1.4"
artifacts = []

[task]
name = "nvidia-demo/{case_id}"
version = "1.0.0"
description = "Offline enterprise evidence task derived from a Hermes trace."
authors = [{{ name = "NVIDIA Demo" }}]
keywords = ["enterprise-assistant", "enterprise-retrieval", "trace-derived"]

[verifier]
timeout_sec = 60.0
environment_mode = "separate"
network_mode = "no-network"

[verifier.environment]
network_mode = "no-network"
build_timeout_sec = 300.0

[agent]
timeout_sec = 120.0

[environment]
network_mode = "no-network"
build_timeout_sec = 300.0
os = "linux"

[solution]
'''


def _readme(case_id: str) -> str:
    return f'''# {case_id}

## Difficulty explanation

The task requires selecting the relevant facts from a multi-application enterprise snapshot while respecting retry, authorization, or approval boundaries where applicable.

## Environment and software requirements

The agent and verifier use the same digest-pinned Python 3.12 slim image with networking disabled. Harbor 0.22.0 and Docker provide isolated execution.

## Ground-truth provenance

Correctness comes from the checked-in fictional world fixture locked by SHA-256, independently of the answer recorded in the source trace.

## Solution explanation

The reference solution writes the minimal structured answer supported by the relevant records in the frozen snapshot.

## Verification explanation

The separate verifier parses the declared answer artifact and compares its objective fields and values with the task's verifier-owned expected output. Missing, malformed, incomplete, and incorrect artifacts fail.

## Relevant experience

This draft applies failure patterns observed in the reviewed Hermes traces and the fixture contract in this repository. A human maintainer must review this section and the generalized task before publication readiness can be claimed.
'''


def _enterprise_query() -> str:
    return '''#!/usr/bin/env python3
import json
import sys
from pathlib import Path

world = json.loads(Path("/opt/enterprise/world.json").read_text())
if len(sys.argv) != 2:
    raise SystemExit("usage: enterprise-query <search text>")
needle = sys.argv[1].casefold()
for collection, records in world.items():
    if not isinstance(records, list):
        continue
    for record in records:
        rendered = json.dumps(record, sort_keys=True)
        if needle in rendered.casefold():
            print(json.dumps({"source": collection, "record": record}, sort_keys=True))
'''


def _test_script() -> str:
    return '''#!/bin/sh
python - <<'PY'
import json
from pathlib import Path

answer_path = Path("/logs/artifacts/answer.json")
expected_path = Path("/tests/expected.json")
try:
    answer = json.loads(answer_path.read_text(encoding="utf-8"))
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    passed = isinstance(answer, dict) and all(answer.get(key) == value for key, value in expected.items())
except (OSError, UnicodeError, json.JSONDecodeError):
    passed = False
Path("/logs/verifier/reward.txt").write_text("1\\n" if passed else "0\\n", encoding="utf-8")
PY
'''


def _negative_agent() -> str:
    return '''from harbor.agents.base import BaseAgent


class IncompleteSolution(BaseAgent):
    SUPPORTS_WINDOWS = False

    @staticmethod
    def name() -> str:
        return "incomplete-solution"

    def version(self) -> str:
        return "1.0.0"

    async def setup(self, environment) -> None:
        return None

    async def run(self, instruction, environment, context) -> None:
        await environment.exec(
            command="mkdir -p /logs/artifacts && printf '%s\\n' '{\\"status\\":\\"unknown\\"}' > /logs/artifacts/answer.json"
        )
'''


def materialize(
    task_root: Path, case_id: str, *, world_path: Path, replace: bool
) -> None:
    case = CASES[case_id]
    task_dir = task_root / case_id
    safe_trace = task_dir / "safe" / "trace.atif.json"
    if _instruction_from_safe_trace(safe_trace) != case.instruction:
        raise ValueError(f"{case_id}: safe trace instruction differs from the frozen task specification")
    candidate_path = task_dir / "candidate.json"
    task_path = task_dir / "task"
    if (candidate_path.exists() or task_path.exists()) and not replace:
        raise FileExistsError(f"{case_id}: candidate/task already exists; pass --replace-draft")
    if replace and task_path.exists():
        shutil.rmtree(task_path)
    reproducibility = task_dir / "reproducibility.json"
    if replace and reproducibility.exists():
        prior_digest = hashlib.sha256(reproducibility.read_bytes()).hexdigest()[:16]
        archive = task_dir / "private" / "superseded" / f"reproducibility-{prior_digest}.json"
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(reproducibility, archive)
        archive.chmod(0o600)
    ground_truth = task_dir / "private" / "ground-truth" / "expected.json"
    digest = _write_json(ground_truth, case.expected, private=True)
    _write_json(
        candidate_path, _candidate(case_id, case, digest, world_path), private=True
    )

    instruction = f"{case.instruction}\n\n{case.output_contract}\n"
    _write(task_path / "instruction.md", instruction)
    _write(task_path / "task.toml", _task_toml(case_id))
    _write(task_path / "README.md", _readme(case_id))
    _write(task_path / "environment" / "Dockerfile", f"FROM {PYTHON_IMAGE}\nWORKDIR /workspace\nCOPY world.json /opt/enterprise/world.json\nCOPY enterprise-query /usr/local/bin/enterprise-query\n")
    shutil.copyfile(world_path, task_path / "environment" / "world.json")
    (task_path / "environment" / "world.json").chmod(0o644)
    _write(task_path / "environment" / "enterprise-query", _enterprise_query(), executable=True)
    _write(
        task_path / "tests" / "Dockerfile",
        f"FROM {PYTHON_IMAGE}\nCOPY . /tests\nWORKDIR /workspace\n",
    )
    _write_json(task_path / "tests" / "expected.json", case.expected)
    _write(task_path / "tests" / "test.sh", _test_script(), executable=True)
    expected_payload = json.dumps(case.expected, indent=2, sort_keys=True) + "\n"
    _write(
        task_path / "solution" / "solve.sh",
        "#!/bin/sh\nmkdir -p /logs/artifacts\ncat > /logs/artifacts/answer.json <<'JSON'\n"
        + expected_payload
        + "JSON\n",
        executable=True,
    )
    _write(task_dir / "private" / "negative_agent.py", _negative_agent(), private=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-root", type=Path, default=DEFAULT_TASK_ROOT)
    parser.add_argument(
        "--world", type=Path, default=ROOT / "fixtures" / "world-v2.json"
    )
    parser.add_argument("--case", action="append", choices=sorted(CASES))
    parser.add_argument("--replace-draft", action="store_true")
    args = parser.parse_args()
    world_path = args.world.resolve()
    if not world_path.is_file():
        parser.error(f"world fixture does not exist: {world_path}")
    try:
        world_path.relative_to(ROOT.resolve())
    except ValueError:
        parser.error("world fixture must be inside the repository")
    selected = args.case or sorted(CASES)
    for case_id in selected:
        materialize(
            args.task_root.resolve(), case_id,
            world_path=world_path, replace=args.replace_draft,
        )
        print(case_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

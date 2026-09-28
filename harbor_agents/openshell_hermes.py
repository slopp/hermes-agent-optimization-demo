"""Run a Harbor Hermes trial in an OpenShell sandbox.

Harbor remains the evaluation orchestrator and separate no-network verifier.
OpenShell owns the untrusted agent process, credential boundary, network policy,
fixture-backed MCP process, and Relay capture. The adapter copies only verifier
artifacts back into the Harbor task environment.
"""

from __future__ import annotations

import asyncio
import shlex
import tempfile
from pathlib import Path
from typing import Any, override

from harbor.agents.installed.base import with_prompt_template
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from harbor_agents.hermes_flywheel import ARM_CONFIG, HermesFlywheel
from harbor_agents.openshell_utils import final_answer, sandbox_name

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE = "hermes-flywheel-openshell:0.1"
DEFAULT_PROVIDER = "hermes-nvidia"
HERMES_VERSION = "0.21.3"


class OpenShellHermesFlywheel(HermesFlywheel):
    """Selectable Hermes arm whose complete agent runtime is OpenShell."""

    def __init__(
        self,
        *args: Any,
        openshell_bin: str = "openshell",
        openshell_image: str = DEFAULT_IMAGE,
        openshell_provider: str = DEFAULT_PROVIDER,
        openshell_policy: str = str(ROOT / "openshell" / "policy.yaml"),
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.openshell_bin = openshell_bin
        self.openshell_image = openshell_image
        self.openshell_provider = openshell_provider
        self.openshell_policy = Path(openshell_policy).expanduser().resolve()

    @staticmethod
    @override
    def name() -> str:
        return "openshell-hermes-flywheel"

    @override
    def version(self) -> str:
        return HERMES_VERSION

    @override
    async def setup(self, environment: BaseEnvironment) -> None:
        """Validate the host runtime; do not install an agent in the task image."""
        del environment
        if not self.openshell_policy.is_file():
            raise RuntimeError(f"OpenShell policy not found: {self.openshell_policy}")
        await self._host_command([self.openshell_bin, "status"], timeout=30)

    async def _host_command(
        self,
        command: list[str],
        *,
        timeout: int = 360,
        check: bool = True,
    ) -> tuple[int, str, str]:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError(
                f"Host command timed out after {timeout}s: {shlex.join(command)}"
            ) from None

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        log_path = self.logs_dir / "openshell.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"$ {shlex.join(command)}\n{stdout}{stderr}\n")
        if check and process.returncode != 0:
            detail = (stderr or stdout or "no output")[-4000:]
            raise RuntimeError(
                f"Host command failed ({process.returncode}): "
                f"{shlex.join(command)}\n{detail}"
            )
        return process.returncode or 0, stdout, stderr

    def _write_runtime(self, runtime_dir: Path, instruction: str) -> None:
        runtime_dir.mkdir(parents=True)
        (runtime_dir / "artifacts" / "relay").mkdir(parents=True)
        hermes_home = runtime_dir / "hermes"
        (hermes_home / "nemo-relay").mkdir(parents=True)

        if not self.model_name or "/" not in self.model_name:
            raise ValueError("Model name must be in provider/model format")
        provider, model = self.model_name.split("/", 1)
        if provider != "nvidia":
            raise ValueError(
                "The tutorial OpenShell profile supports NVIDIA models only; "
                f"received provider {provider!r}"
            )

        config = self._build_config_yaml(model) + '''mcp_servers:
  enterprise-world:
    command: /usr/bin/env
    args:
      - PYTHONPATH=/opt/enterprise
      - python
      - -m
      - pa_style_mock_mcp.mcp_sdk_stdio
      - --world
      - /workspace/run/world.json
      - --call-log
      - /workspace/run/artifacts/tool-calls.jsonl
      - --catalog
      - extended
'''
        (hermes_home / "config.yaml").write_text(
            config, encoding="utf-8"
        )
        (hermes_home / "SOUL.md").write_text(
            ARM_CONFIG[self.arm]["profile"].read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        relay_config = f'''version = 1

[[components]]
kind = "observability"
enabled = true

[components.config]
version = 3

[components.config.atof]
enabled = true

[[components.config.atof.sinks]]
type = "file"
output_directory = "/workspace/run/artifacts/relay/atof"
filename = "events.jsonl"
mode = "append"

[components.config.atif]
enabled = true
output_directory = "/workspace/run/artifacts/relay/atif"
filename_template = "trajectory-{{session_id}}.json"
agent_name = "Hermes-enterprise-world"
agent_version = "{self.arm}"
'''
        (hermes_home / "nemo-relay" / "relay-plugins.toml").write_text(
            relay_config, encoding="utf-8"
        )
        (runtime_dir / "instruction.txt").write_text(instruction, encoding="utf-8")
        (runtime_dir / "world.json").write_text(
            (ROOT / "fixtures" / "world-v2.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        model_arg = shlex.quote(model)
        script = f'''#!/usr/bin/env bash
set -uo pipefail
mkdir -p artifacts/relay
export HERMES_HOME=/workspace/run/hermes
export TERMINAL_ENV=local
export HERMES_NEMO_RELAY_PLUGINS_TOML=/workspace/run/hermes/nemo-relay/relay-plugins.toml
hermes --yolo chat \
  -q "$(cat /workspace/run/instruction.txt)" \
  -Q \
  --model {model_arg} \
  --provider nvidia \
  2>&1 | stdbuf -oL tee /workspace/run/artifacts/hermes.txt
hermes_rc=${{PIPESTATUS[0]}}
hermes sessions export /workspace/run/artifacts/hermes-session.jsonl \
  --source cli 2>/dev/null || true
exit "$hermes_rc"
'''
        (runtime_dir / "run.sh").write_text(script, encoding="utf-8")

    async def _download_optional(
        self, sandbox: str, remote: str, local: Path
    ) -> bool:
        local.parent.mkdir(parents=True, exist_ok=True)
        return_code, _, _ = await self._host_command(
            [self.openshell_bin, "sandbox", "download", sandbox, remote, str(local)],
            timeout=120,
            check=False,
        )
        return return_code == 0

    async def _publish_artifacts(
        self, environment: BaseEnvironment, artifact_dir: Path
    ) -> None:
        await environment.exec("mkdir -p /logs/artifacts/relay", timeout_sec=10)
        for name in ("final-answer.txt", "tool-calls.jsonl", "hermes-session.jsonl"):
            source = artifact_dir / name
            if source.is_file():
                await environment.upload_file(source, f"/logs/artifacts/{name}")
        relay_dir = artifact_dir / "relay"
        if relay_dir.is_dir():
            await environment.upload_dir(relay_dir, "/logs/artifacts/relay")

    async def execute_openshell(self, instruction: str, artifact_dir: Path) -> None:
        """Run one unscored agent turn and retain its deployment artifacts."""
        sandbox = sandbox_name(self.session_id, self.arm)
        run_error: RuntimeError | None = None
        artifact_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="hermes-openshell-") as temp:
            runtime_dir = Path(temp) / "run"
            self._write_runtime(runtime_dir, instruction)
            try:
                await self._host_command(
                    [
                        self.openshell_bin,
                        "sandbox",
                        "create",
                        "--name",
                        sandbox,
                        "--from",
                        self.openshell_image,
                        "--provider",
                        self.openshell_provider,
                        "--policy",
                        str(self.openshell_policy),
                        "--upload",
                        f"{runtime_dir}:/workspace",
                        "--no-git-ignore",
                        "--detach",
                        "--no-tty",
                    ],
                    timeout=180,
                )
                try:
                    await self._host_command(
                        [
                            self.openshell_bin,
                            "sandbox",
                            "exec",
                            "--name",
                            sandbox,
                            "--workdir",
                            "/workspace/run",
                            "--timeout",
                            "360",
                            "--no-login-shell",
                            "--no-tty",
                            "--",
                            "/bin/bash",
                            "run.sh",
                        ],
                        timeout=390,
                    )
                except RuntimeError as exc:
                    run_error = exc

                for name in ("tool-calls.jsonl", "hermes-session.jsonl", "hermes.txt"):
                    await self._download_optional(
                        sandbox,
                        f"/workspace/run/artifacts/{name}",
                        artifact_dir / name,
                    )
                await self._download_optional(
                    sandbox,
                    "/workspace/run/artifacts/relay",
                    artifact_dir / "relay",
                )

                session_path = artifact_dir / "hermes-session.jsonl"
                answer = final_answer(
                    session_path.read_text(encoding="utf-8")
                    if session_path.is_file()
                    else ""
                )
                (artifact_dir / "final-answer.txt").write_text(answer, encoding="utf-8")
                if session_path.is_file():
                    self.logs_dir.mkdir(parents=True, exist_ok=True)
                    (self.logs_dir / "hermes-session.jsonl").write_text(
                        session_path.read_text(encoding="utf-8"), encoding="utf-8"
                    )
                if run_error is not None:
                    raise run_error
            finally:
                await self._host_command(
                    [self.openshell_bin, "sandbox", "delete", sandbox],
                    timeout=60,
                    check=False,
                )

    @with_prompt_template
    @override
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        context.metadata = {
            "runtime": "openshell",
            "image": self.openshell_image,
            "provider": self.openshell_provider,
        }
        with tempfile.TemporaryDirectory(prefix="hermes-openshell-") as temp:
            artifact_dir = Path(temp) / "artifacts"
            await self.execute_openshell(instruction, artifact_dir)
            await self._publish_artifacts(environment, artifact_dir)

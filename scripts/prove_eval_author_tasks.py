#!/usr/bin/env python3
"""Run Eval Author's deterministic Harbor proof matrix for private drafts."""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import subprocess
from pathlib import Path

ARMS = (
    ("nop", "proof-v1-nop-1"),
    ("nop", "proof-v1-nop-2"),
    ("oracle", "proof-v1-oracle-1"),
    ("oracle", "proof-v1-oracle-2"),
    ("negative", "proof-v1-negative-1"),
)

HARBOR_NETWORK_PROBE = (
    "from harbor.environments.docker.docker import DockerEnvironment; "
    "raise SystemExit(0 if DockerEnvironment._egress_control_kernel_support() else 1)"
)


def _run(command: list[str], *, env: dict[str, str], log: Path | None = None) -> None:
    if log is None:
        subprocess.run(command, check=True, env=env)
        return
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as stream:
        subprocess.run(command, check=True, env=env, stdout=stream, stderr=subprocess.STDOUT)


def _check_no_network_support(harbor_python: Path, docker_context: str) -> None:
    """Fail before creating proof receipts when Harbor cannot isolate the jobs."""
    env = {**os.environ, "DOCKER_CONTEXT": docker_context}
    try:
        subprocess.run(
            ["docker", "--context", docker_context, "info"],
            check=True,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise RuntimeError(
            f"Docker context {docker_context!r} is unavailable: {detail.strip()}"
        ) from error

    probe = subprocess.run(
        [str(harbor_python), "-c", HARBOR_NETWORK_PROBE],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode:
        raise RuntimeError(
            f"Docker context {docker_context!r} cannot enforce Harbor 0.22.0 "
            "network_mode='no-network'. Docker Desktop's LinuxKit kernel is a known "
            "incompatible host. On macOS, start Colima and pass --docker-context colima; "
            "otherwise use a native Linux Docker host with CONFIG_NFT_FIB_INET. Do not "
            "weaken the Eval Author task to public networking."
        )


def _proof_arm(
    task_dir: Path,
    arm: str,
    name: str,
    *,
    helper: Path,
    harbor_python: Path,
    harbor: Path,
    docker_context: str,
) -> None:
    env = dict(os.environ)
    env["DOCKER_CONTEXT"] = docker_context
    receipt = [
        str(harbor_python),
        str(helper),
        "record-run-inputs",
        "--task-dir",
        str(task_dir),
        "--arm",
        arm,
        "--job-dir",
        f"private/jobs/{name}",
    ]
    agent = arm
    if arm == "negative":
        agent = "negative_agent:IncompleteSolution"
        receipt.extend(
            [
                "--negative-agent",
                agent,
                "--negative-source",
                "private/negative_agent.py",
                "--negative-rationale",
                "Writes a valid but intentionally incomplete answer without the required case facts.",
            ]
        )
        env["PYTHONPATH"] = str((task_dir / "private").resolve())
    _run(receipt, env=env, log=task_dir / "private" / f"{name}-receipt.log")
    _run(
        [
            str(harbor),
            "run",
            "-p",
            str(task_dir / "task"),
            "-a",
            agent,
            "--jobs-dir",
            str(task_dir / "private" / "jobs"),
            "--job-name",
            name,
            "-y",
            "-q",
        ],
        env=env,
        log=task_dir / "private" / f"{name}.log",
    )


def prove(
    task_dir: Path,
    *,
    helper: Path,
    harbor_python: Path,
    harbor: Path,
    docker_context: str,
    workers: int,
) -> None:
    # record-run-inputs intentionally requires each future job directory not to
    # exist. Harbor creates those leaf directories, but its shared parent must
    # exist before concurrent proof arms start.
    (task_dir / "private" / "jobs").mkdir(parents=True, exist_ok=True)
    _run(
        [str(harbor_python), str(helper), "check-runtime", "--task-dir", str(task_dir)],
        env={**os.environ, "DOCKER_CONTEXT": docker_context},
    )
    _run(
        [str(harbor_python), str(helper), "record-reproducibility", "--task-dir", str(task_dir)],
        env=os.environ.copy(),
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                _proof_arm,
                task_dir,
                arm,
                name,
                helper=helper,
                harbor_python=harbor_python,
                harbor=harbor,
                docker_context=docker_context,
            )
            for arm, name in ARMS
        ]
        for future in futures:
            future.result()
    common = [str(harbor_python), str(helper)]
    _run(
        common
        + [
            "record-validation",
            "--task-dir",
            str(task_dir),
            "--nop-job-dir",
            "private/jobs/proof-v1-nop-1",
            "--nop-job-dir",
            "private/jobs/proof-v1-nop-2",
            "--oracle-job-dir",
            "private/jobs/proof-v1-oracle-1",
            "--oracle-job-dir",
            "private/jobs/proof-v1-oracle-2",
            "--negative-job-dir",
            "private/jobs/proof-v1-negative-1",
            "--harbor-version",
            "0.22.0",
        ],
        env=os.environ.copy(),
    )
    _run(
        common
        + [
            "finalize",
            "--task-dir",
            str(task_dir),
            "--status",
            "candidate",
            "--worked-well",
            "Two Oracle runs passed while two NOP runs and one incomplete-answer control failed cleanly under isolated no-network verification.",
            "--did-not-work",
            "Human review of the generalized task and Relevant experience remains outstanding.",
        ],
        env=os.environ.copy(),
    )
    _run(common + ["check", "--task-dir", str(task_dir)], env=os.environ.copy())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-root", type=Path, required=True)
    parser.add_argument("--case", action="append", required=True)
    parser.add_argument("--helper", type=Path, required=True)
    parser.add_argument("--harbor-python", type=Path, required=True)
    parser.add_argument("--harbor", type=Path, required=True)
    parser.add_argument("--docker-context", default="default")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 5:
        parser.error("--workers must be between 1 and 5")
    try:
        _check_no_network_support(args.harbor_python.absolute(), args.docker_context)
    except RuntimeError as error:
        parser.error(str(error))
    for case_id in args.case:
        prove(
            (args.task_root / case_id).resolve(),
            helper=args.helper.resolve(),
            # Preserve virtual-environment launcher symlinks. Resolving the
            # Python link can escape the venv and make Harbor imports vanish.
            harbor_python=args.harbor_python.absolute(),
            harbor=args.harbor.absolute(),
            docker_context=args.docker_context,
            workers=args.workers,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Hermes agent harness optimization demo

This repository is a hands-on tutorial for improving an enterprise agent harness
from observed behavior: start with realistic traces, author Harbor evaluations
with a coding agent, analyze production and baseline-eval traces with NeMo Trace
Analyst, implement a candidate harness, and compare it with the baseline.

```text
42 production traces → Trace Analyst → Codex + Eval Author → frozen Harbor tasks
                                                                ↓
                                          baseline development runs + scores
                                                                ↓
                                            Trace Analyst → candidate harness
                                                                ↓
                                         baseline/candidate dev + held-out A/B
```

The fictional agent helps a company prepare a product launch by researching
across mail, calendar, chat, files, enterprise knowledge, directory, project,
analytics, support, and connector tools. The deterministic world includes stale
and current records, ambiguous people, pagination, a large structured evidence
register, a disconnected connector, and a transient search failure. These map to
common enterprise services such as Microsoft 365 or Google Workspace, Slack or
Teams, Confluence or SharePoint, Jira or Asana, and ServiceNow or Zendesk.

The tutorial is grounded in NVIDIA's internal work optimizing a production
personal assistant for employee research and actions across those kinds of
systems. The public [Nemotron 3 Ultra harness-profile case study](https://developer.nvidia.com/blog/create-a-langchain-deep-agents-harness-profile-for-nvidia-nemotron-3-ultra-to-improve-performance/)
describes related optimization methods.

## What's included

- 42 checked-in baseline trace examples, one distinct user request each, plus an
  OpenShell trace-generation path for creating a fresh corpus.
- Fictional, deterministic MCP fixtures and a Streamable HTTP MCP server hosted
  on the machine running Harbor—not inside the Hermes sandbox.
- A restrictive OpenShell policy that allows Hermes to reach only the local
  host-bridge MCP ports and the configured model provider. The measured Harbor
  trials exercise this remote-from-the-sandbox HTTP boundary.
- Trace Analyst input adapters/configuration and a Codex workflow using the
  public [NeMo Trace Analyst](https://github.com/NVIDIA-NeMo/labs-trace-intel)
  and [NeMo Eval Author](https://github.com/NVIDIA-NeMo/labs-eval-author)
  repositories.
- Harbor runners, editable baseline/candidate Hermes harnesses, and scripts for
  validating trace provenance and comparing repeated A/B runs.

Eval Author does not pick a fixed suite size or automatically split data. Codex
uses its skills to inspect the traces and Trace Analyst findings, propose
task-worthy cases, and carry out the required reviews. A human reviews the tasks
and freezes development/held-out membership before any candidate changes. Each
task is then run at least three times per arm; the same Harbor task set and
fixture-backed host MCP are used for both arms.

The checked-in task collection is an experimental pilot with human task review
pending. Passing automated controls establishes technical behavior, not task
readiness. See the [reference evidence and limits](docs/results.md).

## Start here

Follow the [walkthrough](docs/walkthrough.md) for prerequisites, copyable host
setup commands, the 10-step flywheel, optional trace regeneration, and the
secondary Trace-Analyst-only path. The ideal full-run host is fresh Ubuntu 24.04
with native Docker, at least 4 vCPUs, 16 GB RAM, 50 GB free disk, and a working
OpenShell gateway; a Brev CPU instance is a convenient option. Harbor's isolated
verifier requires a Linux kernel with `CONFIG_NFT_FIB_INET`, so Docker Desktop is
not the supported full-run environment.

Supporting detail: [fixture world](fixtures/README.md),
[harness patterns](docs/harness-patterns.md), and
[extending the environment for RL](docs/gym-extension.md).

The public example uses synthetic records throughout. Replace the workload,
fixtures, trace adapter, and task environment to apply the same method to a real
agent.

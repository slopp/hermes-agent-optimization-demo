# Optimize an Enterprise Agent Harness with NVIDIA NeMo

This repository is a reproducible, end-to-end tutorial for improving a
tool-using enterprise agent from its execution traces. It starts with a working
Hermes agent and a checked-in trace bundle, turns trace failures into an
evaluation suite, uses NeMo Insights to identify recurring problems, applies
targeted harness changes, and measures the result with a matched A/B test.

The complete loop is:

```text
Hermes agent + mock enterprise tools
        ↓ traces collected by NeMo Relay
trace review + NeMo Eval Author
        ↓ frozen development and held-out evals
NeMo Insights analysis
        ↓ evidence-backed harness changes
baseline/candidate A/B
        ↓
repeat, or promote the environment to NeMo Gym for rollout-scale optimization
```

The primary held-out result in the included experiment was:

| Arm | Pass rate | Mean tool calls | Command timeouts |
| --- | ---: | ---: | ---: |
| Baseline | 25.0% | 20.4 | 1 |
| Optimized harness | 91.7% | 6.0 | 0 |

The model and fictional enterprise data were held constant. The candidate
changed only the agent harness. See [the measured results and
caveats](docs/results.md).

## Grounded in NVIDIA's Personal Assistant

This tutorial is based on patterns encountered while NVIDIA optimized an
internal production agent called **Personal Assistant (PA)**. PA helps NVIDIA
employees answer questions and complete workplace tasks using enterprise
systems such as email, calendar, chat, files, knowledge sources, employee
directory data, and other internal tools. Its work includes multi-source
question answering, research and synthesis, meeting and task workflows,
artifact creation, and actions that may require user approval.

That setting creates agent-harness problems familiar to many enterprise teams:

- selecting the right tools from a large catalog;
- retrieving all necessary sources before answering;
- reading authoritative records after broad search;
- handling large structured results without flooding model context;
- distinguishing authentication, transport, tool, and reasoning failures;
- bounding retries and unnecessary tool use; and
- preventing external actions until the user has approved them.

The repository recreates those problem shapes in a small fictional company. It
does **not** contain the Personal Assistant implementation, production data,
internal tools, employee identities, or NVIDIA evaluation questions. All
published fixtures and tasks are generalized and deterministic. NVIDIA's
public [Nemotron 3 Ultra harness-profile case
study](https://developer.nvidia.com/blog/create-a-langchain-deep-agents-harness-profile-for-nvidia-nemotron-3-ultra-to-improve-performance/)
describes related optimization methodology.

## What you can do with this repository

The default starting point requires no trace generation or production system:

1. Inspect six checked-in traces from real Hermes executions against the mock
   environment.
2. Inspect the trace-derived Eval Author tasks and their verifier proofs.
3. Re-run the deterministic validation and scoring locally.
4. Follow the tutorial to analyze traces with standalone NeMo Insights.
5. Run the baseline and optimized Hermes harnesses against the same frozen
   cases and compare answer quality, tool trajectory, safety, and efficiency.
6. Generate additional traces by running the agent through NemoClaw and the
   mock MCP server.

NeMo Platform is not required. This example uses Eval Author's local
trace-environment workflow and the standalone `insight-agent` CLI. NeMo Gym is
also optional; it becomes useful when moving from offline harness iteration to
large-scale rollouts or model/harness reinforcement learning.

## Repository contents

- [`traces/baseline`](traces/baseline): six compact ATIF traces recorded from
  Hermes against the fictional tools. Any non-fixture local-tool content is
  visibly redacted.
- [`fixtures/world-v1.json`](fixtures/world-v1.json): the frozen fictional
  enterprise world.
- [`src/pa_style_mock_mcp`](src/pa_style_mock_mcp): deterministic tool behavior
  with stdio and Streamable HTTP MCP transports.
- [`evals/flywheel-eval-set-v1.json`](evals/flywheel-eval-set-v1.json): six
  trace-derived cases and four independently frozen held-out variants.
- [`evals/eval-author-products-v1`](evals/eval-author-products-v1): portable
  Eval Author/Harbor tasks with NOP, Oracle, and negative-control proofs.
- [`profiles/nemoclaw-candidate-v3-soul.md`](profiles/nemoclaw-candidate-v3-soul.md):
  the winning harness policy.
- [`results/measured-ab.json`](results/measured-ab.json): machine-readable A/B
  results.

## Start here

For a quick, model-free verification:

```bash
make test
make validate
```

Then follow:

1. [Provision NemoClaw, the mock MCP, Relay, Insights, and Eval
   Author](docs/provisioning.md).
2. [Run the optimization cycle end to end](docs/walkthrough.md).
3. [Study the harness issue/fix patterns](docs/harness-patterns.md).
4. [Promote the mock environment to NeMo Gym when rollout-scale work is
   needed](docs/gym-extension.md).

The checked-in Eval Author products passed their automated privacy checks and
technical verifier proofs. They remain marked `candidate_unproven` until a
human completes the final publication review; the status is preserved in the
artifacts rather than silently treated as approval.

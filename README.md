# Hermes Agent Optimization Flywheel

This example starts where an enterprise agent team usually starts: an agent
already exists and there is a pile of traces. The included traces were emitted
by Hermes in a NemoClaw-managed OpenShell sandbox against a deterministic,
fictional PA-style MCP environment. They are not generated prose and contain no
Personal Assistant production data.

The scenario is grounded in issue and fix patterns observed during NVIT's
internal Personal Assistant harness-optimization work. It is a fictional,
generalized reproduction—not a release of the PA agent, traces, fixtures, or
benchmark. The related public methodology is described in NVIDIA's
[Nemotron 3 Ultra harness-profile case study](https://developer.nvidia.com/blog/create-a-langchain-deep-agents-harness-profile-for-nvidia-nemotron-3-ultra-to-improve-performance/).

From that starting point, the example runs this flywheel:

```text
checked-in traces -> Eval Author -> frozen eval + held-outs -> baseline run
       -> standalone Insights -> harness candidate -> matched A/B -> repeat
```

NeMo Platform is optional. The definitive targets here are Eval Author's local
trace-environment workflow and the standalone `insight-agent` CLI.

## What is included

- [`traces/baseline`](traces/baseline): six real, compact ATIF traces selected
  from the broad baseline. Non-fixture local-tool payloads are visibly redacted.
- [`fixtures/world-v1.json`](fixtures/world-v1.json): the frozen fictional
  enterprise world behind the tools.
- `src/pa_style_mock_mcp`: stdio and Streamable HTTP MCP adapters over that world.
- [`evals/flywheel-eval-set-v1.json`](evals/flywheel-eval-set-v1.json): six
  trace-derived cases plus four independently frozen held-out paraphrases.
- [`evals/eval-author-products-v1`](evals/eval-author-products-v1): the six
  exact Eval Author exports, each with a runnable Harbor task and declassified
  NOP/Oracle/negative-control proof.
- [`profiles/nemoclaw-candidate-v3-soul.md`](profiles/nemoclaw-candidate-v3-soul.md):
  the winning harness policy.
- [`results/measured-ab.json`](results/measured-ab.json): the measured result.

The primary held-out result was 25.0% -> 91.7% pass rate and 20.4 -> 6.0 mean
tool calls. See [the full result and caveats](docs/results.md).

## Local verification

```bash
make test
make validate
make mcp-sdk-check
make streamable-http-check
python3 scripts/validate_trace_manifest.py traces/manifest.json
python3 scripts/validate_trace_derived_suite.py evals/flywheel-eval-set-v1.json
python3 scripts/validate_eval_author_products.py evals/flywheel-eval-set-v1.json
```

The source-trace manifest is intentionally `pending`. Eval Author contextual
privacy review, technical Harbor proof, exact-product agent review, and
automated credential/identity scans passed. The products remain explicitly
`candidate_unproven` until a human reviews the generalized tasks and exact
publication bundle.

## Reproduce the cycle

1. Follow [provisioning](docs/provisioning.md) for NemoClaw, the mock MCP,
   Relay, standalone Insights, and Eval Author.
2. Follow the [end-to-end walkthrough](docs/walkthrough.md).
3. Read [harness patterns](docs/harness-patterns.md) for the PA-grounded issue
   and fix patterns demonstrated here.
4. Read [the Gym extension design](docs/gym-extension.md) when the next step is
   rollout-scale evaluation or model/harness RL.

Data Designer is optional and is used only to expand fictional fixture records;
it must not manufacture traces or judgments. NeMo Gym is also optional at this
stage. Extend the agent/world into a Gym environment when moving from offline
harness iteration to model or harness RL and rollout-scale training. The
extension design is grounded in NVIDIA's official Workplace Assistant resource
server while keeping Gym out of the starting path.

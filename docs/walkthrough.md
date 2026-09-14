# End-to-end walkthrough

This walkthrough reproduces the offline harness-optimization cycle without a
NeMo Platform service. Replace values in angle brackets; never paste keys into
the repository or a command committed to shell history.

## 0. Start from the supplied traces

The normal starting experience does not require a model call:

```bash
python3 scripts/validate_trace_manifest.py traces/manifest.json
python3 scripts/validate_trace_derived_suite.py evals/flywheel-eval-set-v1.json
python3 scripts/validate_eval_author_products.py evals/flywheel-eval-set-v1.json
```

`traces/baseline/*.atif.json` are real Hermes traces. Relay originally emitted
ATOF. Because the tested Hermes 0.20.6 integration did not close the session
event needed for Relay 0.7.2's native ATIF snapshot, the checked-in files were
normalized from completed ATOF turn scopes. Each file records that structural
loss and the public-boundary redaction of non-fixture tool payloads.

## 1. Prepare the local tools

Follow [provisioning](provisioning.md), then set non-secret names:

```bash
export DEMO_GATEWAY='<OpenShell gateway name>'
export DEMO_SANDBOX='<disposable NemoClaw sandbox name>'
export DEMO_MODEL='<one NVIDIA Build model ID>'
export INSIGHTS_REPO='<nemo-platform-insights-preview checkout>'
export NEMO_PLATFORM_REPO='<nemo-platform checkout used only for Eval Author source>'
export DEMO_REPO="$PWD"
```

Build the fictional MCP and verify its contract before spending model calls:

```bash
make test
make validate
make mock-mcp-container-check
```

Deploy/register the Streamable HTTP MCP as described in provisioning and verify
that Hermes discovers the `pa-style-enterprise` tools.

## 2. Recollect the broad baseline (optional)

The checked-in traces are enough for analysis. Recollection is optional and is
useful when testing another model or Hermes version.

Configure a fresh Relay arm and the broad baseline:

```bash
python3 scripts/configure_nemoclaw_arm.py \
  --gateway "$DEMO_GATEWAY" --sandbox "$DEMO_SANDBOX" \
  --arm baseline --trace-label baseline-repro

python3 scripts/run_nemoclaw_matrix.py \
  --gateway "$DEMO_GATEWAY" --sandbox "$DEMO_SANDBOX" \
  --arm baseline --trials 3 --reset-demo-sessions \
  --model "$DEMO_MODEL" --provider nvidia-prod \
  --output .runs/baseline-repro/responses
```

Use a disposable sandbox with `--reset-demo-sessions`; the option deliberately
deletes prior Hermes sessions before each case. Do not point it at a personal or
production sandbox.

Download the Relay ATOF file using OpenShell, then convert completed turns:

```bash
mkdir -p .runs/baseline-repro/relay
openshell -g "$DEMO_GATEWAY" sandbox download "$DEMO_SANDBOX" \
  /sandbox/pa-flywheel-traces/baseline-repro/atof/events.jsonl \
  .runs/baseline-repro/relay

python3 scripts/convert_atof_to_atif.py \
  --atof .runs/baseline-repro/relay/events.jsonl \
  --output-dir .runs/baseline-repro/atif

python3 scripts/convert_atof_for_insights.py \
  --atof .runs/baseline-repro/relay/events.jsonl \
  --matrix experiments/fidelity-matrix.json \
  --output .runs/baseline-repro/insights.jsonl
```

Always inspect requested and returned model IDs in Relay. During development,
the gateway returned Ultra despite accepting a Lightning alias; the measured
result therefore names the returned Ultra model.

## 3. Run standalone Insights

Validate the canonical corpus and inspect deterministic coverage:

```bash
cd "$INSIGHTS_REPO"
.venv/bin/insight-agent validate \
  --traces "$DEMO_REPO/.runs/baseline-repro/insights.jsonl"
.venv/bin/insight-agent coverage \
  "$DEMO_REPO/.runs/baseline-repro/insights.jsonl" --with-findings
```

Create a small YAML config using the checked-in example, set the trace and
output paths, then run:

```bash
.venv/bin/insight-agent --config <absolute-config.yaml>
```

Inspect both `anomaly_and_patterns/digest.md` and `tool_issues/cards.md`. Do not
treat an anomaly as a defect without opening the cited traces. In the tested
preview, deterministic verdict groups are not forwarded automatically to the
LLM Analyst, and dynamically discovered MCP calls may appear as unknown tools.

The broad traces should expose recurring PA-style patterns: local/session
exploration instead of enterprise retrieval, missing sources in compound
questions, search without read, unbounded retry, direct large-result handling,
and failure to use prepare-only actions.

## 4. Prepare trace-derived eval material with Eval Author

The checked-in manifest has six members. Run Eval Author from its source
checkout; no Platform workspace is involved:

```bash
EA="$NEMO_PLATFORM_REPO/plugins/nemo-eval-author/skills/eval-author-trace-environment/scripts/trace_environment.py"
EAPY="$NEMO_PLATFORM_REPO/.venv/bin/python"

"$EAPY" "$EA" batch-prepare \
  --root .eval-author/public-trace-environments \
  --manifest traces/eval-author-batch.json
"$EAPY" "$EA" batch-status \
  --root .eval-author/public-trace-environments \
  --manifest traces/eval-author-batch.json
```

Review every string and privacy-audit finding in each task, then record the
review with `review-privacy`. Next, materialize the portable offline candidates:

```bash
python3 scripts/materialize_eval_author_tasks.py
```

The materializer refuses to replace drafts by default and confirms each task's
instruction against its reviewed safe ATIF. It gives the Harbor environment a
frozen enterprise snapshot; it does not use the recorded model answer as ground
truth.

Prove one candidate with two NOPs, two Oracles, and an incomplete-answer
negative control. Use a Docker context that can enforce `no-network`:

```bash
python3 scripts/prove_eval_author_tasks.py \
  --task-root .eval-author/public-trace-environments \
  --case source-coverage \
  --helper "$EA" \
  --harbor-python "$DEMO_REPO/.harbor-venv/bin/python" \
  --harbor "$DEMO_REPO/.harbor-venv/bin/harbor" \
  --docker-context colima
```

Repeat `--case` for the other manifest members. The proof script finalizes each
candidate without claiming human review. Follow Eval Author's
`prepare-publication`, `review-publication`, and `export` commands only after
inspecting the exact private preview. The checked-in exports are under
`evals/eval-author-products-v1`; all six have technical status `passed` but
remain `unproven` pending human review.

The resulting frozen suite is `evals/flywheel-eval-set-v1.json`: six cases
linked to both source traces and exact Eval Author products, plus four held-out
fixture-backed paraphrases. Data Designer may expand fictional fixture records,
but it must not generate traces or judgments.

## 5. Measure the candidate

Candidate v3 applies the patterns that emerged from the traces: an evidence
phase, schema/canonical-ID checks, search-then-read, bounded JSON reads, one
identical retry, prepare-without-send, irrelevant-tool downsampling, and a
bounded turn budget.

```bash
python3 scripts/configure_nemoclaw_arm.py \
  --gateway "$DEMO_GATEWAY" --sandbox "$DEMO_SANDBOX" \
  --arm candidate-v3 --trace-label candidate-v3-repro

python3 scripts/run_nemoclaw_matrix.py \
  --gateway "$DEMO_GATEWAY" --sandbox "$DEMO_SANDBOX" \
  --arm candidate --trials 3 --reset-demo-sessions \
  --model "$DEMO_MODEL" --provider nvidia-prod \
  --output .runs/candidate-v3-repro/responses
```

Download and convert its Relay ATOF exactly as for the baseline. Score both
canonical corpora, excluding only provider errors that terminated a turn;
recovered transient retries remain visible and count:

```bash
python3 scripts/score_insights_traces.py --valid-only \
  --suite evals/flywheel-eval-set-v1.json \
  --arm baseline=.runs/baseline-repro/insights.jsonl \
  --arm candidate-v3=.runs/candidate-v3-repro/insights.jsonl \
  --output .runs/development-ab.json
```

## 6. Run the held-out gate

Repeat both arms with `--matrix experiments/held-out-matrix.json`, keeping the
same model, provider, fixture, timeouts, and trial count. Convert with that
matrix and score against the same suite. Do not claim improvement unless the
held-out pass rate improves without answer, trajectory, approval, or runtime
guardrail regression.

The measured run passed this gate: baseline 25.0% vs candidate 91.7%, and mean
tool calls 20.4 vs 6.0. See [results](results.md) for the exact caveats.

## 7. Where Gym belongs

This offline cycle is enough for harness iteration. Extend the same fixture and
tool registry into a NeMo Gym environment when the next objective is rollout
generation at training scale, model/harness RL, or a reproducible interactive
environment benchmark. Users should not need to learn Gym merely to inspect the
starting traces and run the first A/B. The concrete component mapping, reward
contract, parity gates, and rollout boundary are in the
[Gym extension design](gym-extension.md).

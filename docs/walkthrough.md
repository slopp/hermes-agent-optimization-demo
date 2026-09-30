# Walkthrough: traces to a better Hermes harness

This tutorial starts with an agent and traces from it. The checked-in corpus lets
you begin immediately; regenerating traces is optional. The flywheel is:

```text
42 distinct baseline traces ──→ Trace Analyst ──────┐
                                  production report  │
                                                    ├→ Codex + Eval Author → Y Harbor tasks
baseline development runs ──→ Trace Analyst ───────┘                         │
                               eval report                                      ↓
                                           candidate ← both reports → repeated A/B
```

`X` is the number of distinct production requests (42 in this example). `Y` is
the number of reviewed, independently testable Harbor tasks; Eval Author does
not set a quota, and its result may be smaller than the number of Insights or
source traces. `K` is the number of measured attempts per task and arm (`K ≥ 3`
here). With `D` development tasks and `H` held-out tasks, the complete measured
comparison is `2 × K × (D + H)` attempts across both arms. The baseline-
development runs from Step 6 are reused in Step 9, so the remaining work after
Step 6 is `K × (D + 2H)` candidate/dev and both arms/held-out. This is
a repeatability check, not a strong statistical-significance claim.

The main path runs Hermes inside OpenShell. Each trial starts a separate,
authenticated Streamable HTTP mock MCP service on the host running Harbor. Hermes
reaches it as a remote service at `host.openshell.internal:8765` or `:8766`,
allowed by `openshell/policy.yaml`; the MCP process, package, fixture, and call
logs are not inside the OpenShell sandbox. Do not replace this with an in-sandbox
stdio MCP for measured runs. Eval Author's offline NOP/Oracle task proofs are a
separate validation phase; they do not substitute for the OpenShell A/B.

## Before you start

Use a fresh Ubuntu 24.04 Linux host with native Docker, 4+ vCPUs, 16+ GB RAM,
50+ GB free disk, and a working systemd user session. An 8-vCPU Brev CPU instance
is a convenient setup. Harbor 0.22.0's isolated verifier requires Linux
`CONFIG_NFT_FIB_INET`; Docker Desktop's LinuxKit VM is not supported for the full
run. Install OpenShell 0.1.2 for the current checked-in policy and use the same
host for Harbor, OpenShell, Relay artifacts, and the local MCP server.

You also need Git, `curl`, `jq`, `make`, `uv`, Node.js 22.20+ / `npx`, Codex,
and an NVIDIA inference key. Use a key and endpoint appropriate to your
environment; the public tutorial uses the NVIDIA Build endpoint. Do not commit
keys or `.env` files.

### 1. Set up the runtime and freeze the baseline

**Purpose:** make the model, Hermes, fixture, task world, and sandbox policy
identical across all runs. **Output:** a recorded baseline and passing local
preflight; no harness edits yet.

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git jq make
if ! command -v docker >/dev/null; then curl -fsSL https://get.docker.com | sudo sh; fi
sudo usermod -aG docker "$USER"
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
```

If Docker was installed or your group membership changed, reconnect to the host
before continuing. Then:

```bash
git clone https://github.com/slopp/hermes-agent-optimization-demo.git
cd hermes-agent-optimization-demo
docker info >/dev/null
make test
make validate

curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | \
  OPENSHELL_VERSION=v0.1.2 sh
openshell --version
openshell status
openshell doctor check

docker build -f openshell/Dockerfile -t hermes-flywheel-openshell:0.3 .
uv venv .mcp-venv --python 3.12
uv pip install --python .mcp-venv/bin/python -e '.[remote-mcp]'
uv venv .harbor-venv --python 3.12
uv pip install --python .harbor-venv/bin/python 'harbor==0.22.0'
.harbor-venv/bin/harbor --version
```

Provide the Build key without putting it in shell history, and let OpenShell
store it as a credential reference. The sandbox gets no raw key:

```bash
printf 'NVIDIA Build API key: '
read -rs NVIDIA_API_KEY
printf '\n'
export NVIDIA_API_KEY
openshell profile lint -f openshell/provider-nvidia.yaml
openshell profile import -f openshell/provider-nvidia.yaml
openshell provider create --name hermes-nvidia --type hermes-nvidia \
  --credential NVIDIA_API_KEY
unset NVIDIA_API_KEY
```

The checked-in profile permits the model endpoint; the separate OpenShell policy
allows only the two local host-bridge MCP ports. Harbor verifier containers
remain separately isolated and no-network.

### 2. Start from the production-like traces (X)

**Purpose:** give the workflow a real behavior corpus before authoring evals.
**Input:** 42 distinct baseline requests across six behavior families in
`experiments/production-trace-matrix-v3.json`. **Output:** 42 source traces with
Relay data and a provenance index. These are not Harbor tasks or eval scores.

The checked-in `traces/world-v3/production/` corpus is the reproducible default.
Inspect its size and diversity:

```bash
python3 scripts/validate_trace_corpus.py traces/world-v3/production/index.json
jq '{trace_count: (.traces | length), families: ([.traces[].behavior_family] | unique)}' \
  traces/world-v3/production/index.json
```

To create fresh traces instead, run the unchanged baseline against the same
fictional world. This starts a host-side HTTP MCP service for every run, then
Hermes uses it from a short-lived OpenShell sandbox under the allowlist policy:

```bash
.harbor-venv/bin/python scripts/generate_openshell_traces.py \
  --matrix experiments/production-trace-matrix-v3.json \
  --attempts 1 --output .runs/source-traces
.harbor-venv/bin/python scripts/convert_atof_for_insights.py \
  --atof .runs/source-traces \
  --matrix experiments/production-trace-matrix-v3.json \
  --output .runs/production-insights-input.jsonl
.harbor-venv/bin/python scripts/normalize_insights_trace_bundle.py \
  --source production=.runs/production-insights-input.jsonl \
  --matrix experiments/production-trace-matrix-v3.json \
  --output .runs/production-corpus
python3 scripts/validate_trace_corpus.py .runs/production-corpus/index.json
```

Do not increase trace count by repeating the same requests. Fix infrastructure
failures and retain their failure denominator rather than silently dropping
them. Use one complete corpus for the rest of the run; do not mix fresh and
checked-in traces. If you used fresh outputs, tell Codex to use
`.runs/production-corpus/index.json` and the ATIF files under
`.runs/production-corpus/` instead of the checked-in corpus paths in the prompt.

### 3. Run Trace Analyst on production traces

**Purpose:** find recurring behaviors before the eval tasks or candidate exist.
**Input:** the whole canonical production trace JSONL. **Output:** a YAML
Insights report with evidence references. The report is a set of hypotheses,
not an automatic patch or a task list.

Install the public [NeMo Trace Analyst](https://github.com/NVIDIA-NeMo/labs-trace-intel)
CLI at the version used for this walkthrough:

```bash
uv tool install \
  'insight-agent @ git+https://github.com/NVIDIA-NeMo/labs-trace-intel.git@2a62a7787e0b1e22d8b2aa2b75e249e55389beb2'
```

The model key must be available as `INSIGHT_AGENT_API_KEY`; Trace Analyst uses
the model and NVIDIA endpoint from `configs/trace-analyst.yaml`. Set the key
interactively if it is not already in your environment:

```bash
printf 'NVIDIA API key for Trace Analyst: '
read -rs INSIGHT_AGENT_API_KEY
printf '\n'
export INSIGHT_AGENT_API_KEY
```

Run it on either the checked-in corpus or your freshly generated input:

```bash
insight-agent --config configs/trace-analyst.yaml \
  --trace.filesystem.path .runs/production-insights-input.jsonl \
  --output-path results/production-insights.yml
```

For the checked-in corpus, use its companion canonical input at
`traces/world-v3/production/insights.jsonl`. Read the terminal's **Completed**
and **Skipped** evidence-stream summary and inspect `results/production-insights.yml`.
The file is YAML, not JSON; each finding should name supporting trace IDs. Verify
those IDs and examples in the corpus. A skipped stream or no findings is a result
to investigate, not a successful optimization signal.

### 4. Ask Codex and Eval Author to propose and prove Harbor tasks

**Purpose:** convert useful production findings and representative trace evidence
into executable, independently graded Harbor tasks. **Inputs:** the full corpus,
production Insights, `ETHOS.md`, and the tool/fixture implementation. **Output:**
private task drafts, proofs, and a proposed eval-set manifest. `Y` is not fixed:
keep only distinct cases with grounded expectations and a viable environment.

Install the public [NeMo Eval Author](https://github.com/NVIDIA-NeMo/labs-eval-author)
skills into this repo for Codex:

```bash
repo_root="$PWD"
git clone https://github.com/NVIDIA-NeMo/labs-eval-author.git "$HOME/labs-eval-author"
git -C "$HOME/labs-eval-author" checkout 542229dce6055a24527560bd8e0716e07ea5a78b
cd "$repo_root"
npx skills add "$HOME/labs-eval-author" --skill '*' --agent codex --yes --copy
npx skills list --agent codex
codex
```

In Codex, ask it to use Eval Author's trace-environment workflow from
`prompts/eval-author-from-traces.md`. It must inspect the Insights evidence and
source traces, report candidate/no-candidate decisions, use the actual fixture-
backed MCP implementation, and retain Eval Author's privacy and Harbor proof
artifacts. Eval Author's NOP/Oracle proofs validate task behavior; they do not
measure Hermes. The candidate Harbor trials in later steps use the same real
Streamable HTTP MCP service hosted outside OpenShell.

Review each proposed task and the proposed count `Y`. Tasks must have a
trace-backed request, objective expectations, valid ground truth, and no
unresolved privacy, environment, or tool-access decisions. Do not put speculative
tasks into the measured suite just to reach a round number.

Eval Author marks these trace-derived outputs experimental. Its proof receipt
and a Codex privacy pass do not equal human task/relevant-experience review or
the separate exact-content publication review. Complete those human gates before
exporting or checking task products into a public suite; keep pending drafts in
`.eval-author/` and stop at the review step if approval is not available.

### 5. Freeze the development and held-out split

**Purpose:** reserve a fair generalization check before the candidate exists.
**Input:** only the reviewed, runnable Eval Author tasks. **Output:** a frozen
suite manifest with unique task IDs, unique source trace references, split labels,
and hashes. Eval Author creates and validates individual tasks; Codex and a human
reviewer choose `development` versus `held_out` and record why.

Create both splits from the accepted candidates before touching either Hermes
arm. Keep held-out prompt text, fixture-specific answers, and task IDs out of the
candidate design session. This is a protocol holdout, not a security boundary if
all files are visible in the same checkout. Run:

```bash
python3 scripts/validate_trace_derived_suite.py evals/flywheel-eval-set-v3.json
python3 scripts/materialize_harbor_tasks.py --suite evals/flywheel-eval-set-v3.json \
  --output .runs/task-build
```

If a proposed task fails proof, revise or reject it before freezing the split.
Record `D`, `H`, source trace IDs, supporting Insights refs, Eval Author task
paths, proof state, reviewer, split, and artifact digests in the manifest.

### 6. Measure the unchanged baseline on development tasks

**Purpose:** learn which selected behaviors the current harness fails and create
scored Relay trajectories. **Input:** frozen development tasks. **Output:** `K`
rollouts per dev task, Harbor rewards/verifier findings, MCP call logs, and Relay
ATOF/ATIF traces. No candidate changes are allowed yet.

```bash
.harbor-venv/bin/python scripts/run_harbor_eval.py \
  --arm baseline --split development --attempts 3 \
  --job-name baseline-development-k3
.harbor-venv/bin/python scripts/summarize_harbor_job.py \
  .runs/harbor/baseline-development-k3 \
  --output .runs/baseline-development-summary.json
```

Set `--attempts` to the same `K ≥ 3` for every task. Inspect exceptions and
missing Relay exports; infrastructure failures are not agent failures. Keep the
entire `Y_dev × K` set rather than selecting only failures.

### 7. Run Trace Analyst on scored baseline development traces

**Purpose:** learn which behaviors the actual baseline fails on the authored
suite. **Input:** every baseline development trajectory joined to its Harbor
reward and verifier evidence. **Output:** a second report. It complements the
production report; it does not replace it.

Convert the Relay ATIF files in the Harbor job into Trace Analyst's canonical
JSONL format. The converter joins each trace to Harbor's recorded reward and
verifier report; validate the complete `D × K` denominator before analysis:

```bash
.harbor-venv/bin/python scripts/convert_atif_for_insights.py \
  .runs/harbor/baseline-development-k3 \
  --output .runs/baseline-development-insights.jsonl
.harbor-venv/bin/python scripts/validate_scored_trace_bundle.py \
  .runs/baseline-development-insights.jsonl --minimum-attempts 3
insight-agent --config configs/trace-analyst.yaml \
  --trace.filesystem.path .runs/baseline-development-insights.jsonl \
  --output-path results/baseline-development-insights.yml
```

Read the report together with Harbor's per-task verifier reports and the actual
Relay trajectories. Preserve successes as counter-evidence. A pattern in one
failure is not automatically a general harness rule.

### 8. Build and freeze a candidate from both reports

**Purpose:** turn evidence into a small, testable harness hypothesis. **Inputs:**
production Insights + its source traces, scored development Insights + verifier
reports, and the frozen task suite. **Output:** an editable candidate Hermes
profile/runtime and a recorded diff/hash.

Ask Codex to propose a minimal change that responds to findings supported by
both the real production-like corpus and baseline eval runs. A finding can be
used if only one report supports it, but label the evidence and expected scope
honestly. Candidate changes may include phase/state checks, evidence-completeness
gates, tool-list downsampling with discovery, search-then-read sequencing,
schema-first bounded JSON inspection, bounded retry/fallback behavior, or
approval boundaries—but only when the traces justify them. Do not change the
model, task text, fixture, verifier, task set, or OpenShell policy between arms.

Save the hypothesis, report/trace references, files changed, and hashes before
opening held-out results. Review that the implementation changes only harness
behavior, for example `profiles/candidate-soul.md` and the arm config in
`harbor_agents/hermes_flywheel.py`.

### 9. Run the paired A/B on development and held-out

**Purpose:** test whether the candidate fixes the observed dev problem and
generalizes. **Input:** same frozen tasks, fixture, model, network policy, and
`K` attempts. **Output:** paired baseline/candidate measurements for both splits.

The Step 6 baseline development job is reused only if no workload, model, or
environment input changed. Run candidate development and both held-out arms now:

```bash
.harbor-venv/bin/python scripts/run_harbor_eval.py \
  --arm candidate --split development --attempts 3 --job-name candidate-development-k3
.harbor-venv/bin/python scripts/run_harbor_eval.py \
  --arm baseline --split held-out --attempts 3 --job-name baseline-heldout-k3
.harbor-venv/bin/python scripts/run_harbor_eval.py \
  --arm candidate --split held-out --attempts 3 --job-name candidate-heldout-k3
```

Use the same `K` and concurrency for both arms. Never iterate against the
held-out results; if a change is made after opening them, the set is no longer
held out and needs a new frozen sample.

### 10. Decide whether the optimization worked

**Purpose:** report a result that an agent developer can trust. **Inputs:** all
Harbor rewards, verifier details, Relay traces, MCP logs, and the candidate diff.
**Output:** reproducible comparison and go/no-go decision.

Compare per-task and aggregate success, paired attempt outcomes, answer/source
coverage, tool-call counts, exceptions, latency/cost if available, and safety
guardrails such as no unapproved sends. Require improvement on the development
set and no regression on held-out; show uncertainty at `K=3` and avoid claiming
significance from a tiny pilot. If candidate improves dev but not held-out, say
so and keep it as a hypothesis rather than declaring victory.

```bash
.harbor-venv/bin/python scripts/summarize_harbor_job.py \
  .runs/harbor/candidate-development-k3
.harbor-venv/bin/python scripts/summarize_harbor_job.py \
  .runs/harbor/candidate-heldout-k3
.harbor-venv/bin/python scripts/compare_harbor_jobs.py \
  --suite evals/flywheel-eval-set-v3.json --attempts 3 \
  --baseline-development .runs/harbor/baseline-development-k3 \
  --candidate-development .runs/harbor/candidate-development-k3 \
  --baseline-held-out .runs/harbor/baseline-heldout-k3 \
  --candidate-held-out .runs/harbor/candidate-heldout-k3 \
  --output results/measured-ab-v3.json
```

The checked-in `results/` artifacts should include the exact corpus, task split,
both Insights reports, candidate diff/proposal, all run summaries, artifact
hashes, and a paired comparison. `make validate` checks that the recorded
provenance and task denominators still agree.

## Secondary path: just try Trace Analyst

To explore Trace Analyst without Docker, OpenShell, Harbor, or Eval Author, install
it from its public repository and analyze the checked-in production traces:

```bash
uv tool install \
  'insight-agent @ git+https://github.com/NVIDIA-NeMo/labs-trace-intel.git@2a62a7787e0b1e22d8b2aa2b75e249e55389beb2'
printf 'NVIDIA API key for Trace Analyst: '
read -rs INSIGHT_AGENT_API_KEY
printf '\n'
export INSIGHT_AGENT_API_KEY
insight-agent --config configs/trace-analyst.yaml \
  --trace.filesystem.path traces/world-v3/production/insights.jsonl \
  --output-path .runs/production-insights.yml
```

Read [Trace Analyst's results guide](https://github.com/NVIDIA-NeMo/labs-trace-intel/blob/main/docs/results.md): output is YAML, each insight has evidence trace IDs, and completed/skipped evidence streams matter. This path stops after analysis; Eval Author and Harbor are optional unless you want to test changes.

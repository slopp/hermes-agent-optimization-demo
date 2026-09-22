# Trace-to-harness optimization flywheel

This tutorial starts with traces from a Hermes agent running in an OpenShell
sandbox and ends with a measured harness improvement. The checked-in world and MCP
tools are synthetic; the workflow is the same one an enterprise agent team can use
with its own traces and services.

You will learn how to:

1. turn representative agent traces into executable Harbor tasks with Codex and
   NeMo Eval Author;
2. evaluate the unchanged baseline agent and capture scored Relay traces;
3. use NeMo Trace Analyst to connect recurring behavior to failed evals;
4. express a hypothesis as an editable Hermes harness arm; and
5. compare baseline and candidate on development and held-out tasks.

## Choose a path

| Path | What you run | Requirements | Typical time |
| --- | --- | --- | ---: |
| Read the example | Inspect artifacts and measured results | Git | 15 minutes |
| Analyze scored traces | Reuse the checked-in baseline rollouts; run Trace Analyst | Git, `uv`, NVIDIA API key | 15–30 minutes |
| Reproduce the flywheel | Reuse source traces and tasks; run baseline, analysis, candidate, and held-out evals | Linux, Docker, `uv`, NVIDIA API key | 1–2 hours |
| Re-author the eval | Have Codex apply Eval Author to the source traces before running the flywheel | Full path plus Node.js and Codex | add 1–2 hours and reviews |
| Bring your agent | Replace the trace corpus, task tools, and Harbor adapter | Relay-compatible ATIF plus your test environment | project dependent |

The fastest useful path reuses the checked-in Eval Author tasks. Re-authoring is
optional because evaluation design requires human judgment and is not necessary to
verify the later A/B. Trace Analyst-only readers can skip Docker and Harbor.

## Contents

1. [Set up the host](#1-set-up-the-host)
2. [Inspect the starting traces](#2-inspect-the-starting-traces)
3. [Optionally re-author the eval](#3-optionally-re-author-the-eval-with-codex)
4. [Understand the Harbor tasks](#4-understand-and-validate-the-harbor-tasks)
5. [Run the baseline](#5-run-the-baseline-development-eval)
6. [Analyze scored failures](#6-analyze-the-scored-baseline-traces)
7. [Build the candidate](#7-turn-the-findings-into-a-candidate-arm)
8. [Run the A/B](#8-run-the-development-ab)
9. [Open the held-out set](#9-freeze-the-candidate-and-open-the-held-out-set)

## 1. Set up the host

For the full path, use a fresh Ubuntu 24.04 host with native Docker, at least 4
vCPUs, 16 GB RAM, and 50 GB free disk. An 8-vCPU Brev CPU instance is a convenient
reference environment. Harbor 0.22.0's isolated verifier jobs require a Linux
kernel with `CONFIG_NFT_FIB_INET`; Docker Desktop's LinuxKit VM is not compatible.

Install the host dependencies and clone the repository:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git jq make docker.io
sudo usermod -aG docker "$USER"
newgrp docker
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

git clone https://github.com/slopp/hermes-agent-optimization-demo.git
cd hermes-agent-optimization-demo
docker info >/dev/null
make test
make validate
```

`make test` runs the repository's unit tests. `make validate` separately checks the
fixture digest, tool/eval contract, trace index, task metadata, and a clean rebuild
of all Harbor tasks. A successful final line has no `diff` output.

For model-backed steps, enter an NVIDIA API key without echoing it:

```bash
printf 'NVIDIA API key: '
read -rs NVIDIA_API_KEY
printf '\n'
export NVIDIA_API_KEY
```

Install the pinned Harbor runtime only if you will run evals:

```bash
uv venv .harbor-venv --python 3.12
uv pip install --python .harbor-venv/bin/python 'harbor==0.22.0'
.harbor-venv/bin/harbor --version
```

Expected output includes `harbor, version 0.22.0`. The first task image build can
take 10–20 minutes; later tasks reuse the image layers.

## 2. Inspect the starting traces

**Why:** an optimization flywheel needs observed behavior, not a hand-written list
of presumed failures.

**Input:** 36 Relay-compatible ATIF trajectories in
`traces/world-v2/corpus/`. They represent repeated Hermes runs against the same
fixture-backed enterprise tools. They are source evidence, not eval results.

**Output:** a bounded, reviewable corpus that Eval Author can inspect.

```bash
jq '{trace_count: (.traces | length), indexed_groups:
  ([.traces[].logical_case_id] | group_by(.) |
   map({key: .[0], value: length}) | from_entries)}' \
  traces/world-v2/corpus/index.json
find traces/world-v2/corpus -name '*.atif.json' | wc -l
```

Expected counts are 36 traces and six indexed groups with six traces each. Those
labels make the example auditable; an authoring agent must still inspect the traces
and justify which recurring behaviors deserve tasks.

In your own deployment, instrument Hermes with NeMo Relay and export ATIF. Keep
task text, tool calls/results, stable trace IDs, and enough model context to explain
the behavior. Replace `traces/world-v2/corpus/` and its index with that export. You
do not need to generate traces before trying this repository.

## 3. Optionally re-author the eval with Codex

**Why:** NeMo Eval Author is a set of coding-agent skills for turning selected trace
evidence into portable, reviewable evaluations. It is not a command that clusters a
corpus automatically. Codex inspects the corpus, proposes a finite behavior
denominator, selects representative traces, and applies the trace-environment skill
one trace at a time.

**Input:** source traces, the repository ethos, and a human reviewer.

**Output:** Harbor task candidates with an isolated environment, agent instruction,
Oracle, negative controls, verifier, and provenance receipts.

**Skip:** reuse `evals/harbor-tasks-v2/` and continue to step 4.

Install Node.js 22+, Codex, and the Eval Author skills:

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
npm install -g @openai/codex
npx skills add NVIDIA-NeMo/labs-eval-author --skill '*' --agent codex --yes
npx skills list --agent codex
codex
```

At the Codex prompt, paste `prompts/eval-author-from-traces.md`. The prompt tells
Codex to read the installed skills, inspect every indexed trace, report its coverage
denominator and selection rationale, and stop at the skills' human review gates.

The reviews are deliberate. A person must decide whether a trace is safe to use,
which source tools a candidate task may access, whether the generalized task still
tests the intended behavior, and whether the final artifact can be published. In
this example, MCP calls are classified as `real`: the service is synthetic, but the
agent truly discovers and invokes the same task-local server used by the verifier.
Calling it `mock` would mean exact replay or a substituted response mechanism,
which would not test the harness behavior.

For your agent, replace the fixture server with a safely isolated test version of
your actual tool contract. Do not give a Harbor task production credentials.

## 4. Understand and validate the Harbor tasks

Harbor is the execution harness for the eval. Each task builds an isolated Docker
environment, starts the fixture-backed MCP server, presents one instruction to
Hermes, and runs a separate no-network verifier. The verifier checks final-answer
facts, actual calls and arguments, call budgets, retries, and mutation state.

The checked-in suite contains six development tasks chosen from the source corpus
and four separately worded held-out tasks. This means:

- one development attempt is 6 trials per arm;
- three development attempts are 18 trials per arm; and
- three held-out attempts are 12 trials per arm.

Inspect one complete task:

```bash
sed -n '1,180p' evals/harbor-tasks-v2/source-coverage/task.toml
sed -n '1,220p' evals/harbor-tasks-v2/source-coverage/tests/verify.py
```

Confirm that the checked-in tasks reproduce from the shared source:

```bash
python3 scripts/materialize_harbor_tasks.py \
  --output .runs/reference-task-rebuild
diff -qr -x __pycache__ -x '*.pyc' \
  evals/harbor-tasks-v2 .runs/reference-task-rebuild
```

No `diff` output is success. During authoring, Eval Author also requires NOP to
fail, Oracle to pass, relevant negative controls to fail, and the verifier to run
separately without network access. Those controls prove task mechanics; they do not
measure Hermes. The A/B scores below come only from real Hermes trials.

## 5. Run the baseline development eval

**Why:** Trace Analyst is most useful when traces include evaluator outcomes. First
run the unchanged agent on the development tasks, then analyze what failed.

**Input:** six development Harbor tasks and the baseline arm.

**Output:** Harbor rewards and Relay ATIF for six evaluated Hermes rollouts.

```bash
python3 scripts/run_harbor_eval.py \
  --arm baseline --split development --attempts 1 --concurrency 2 \
  --harbor .harbor-venv/bin/harbor --job-name baseline-development

python3 scripts/summarize_harbor_job.py \
  .runs/harbor/baseline-development \
  --output .runs/harbor/baseline-development-summary.json
jq '{passed: .counts.passed, trials: .counts.total,
     pass_rate: .mean_reward, tool_calls: .tool_calls.total,
     exceptions: .counts.exceptions}' \
  .runs/harbor/baseline-development-summary.json
```

The reference smoke run reports `1/6` passing, 30 tool calls, and no infrastructure
exceptions. Model outputs vary, so your exact score can differ. A zero verifier
reward is an agent failure; keep it in the denominator. An environment or provider
exception is infrastructure and should be diagnosed separately.

## 6. Analyze the scored baseline traces

**Why:** Trace Analyst correlates trajectory patterns with evaluator results. This
is the bridge from “the score is low” to a harness hypothesis.

**Input:** baseline Relay trajectories joined with their Harbor rewards.

**Output:** cited, recurring problems to investigate—not automatic fixes.

If you skipped Harbor, use the checked-in scored baseline bundle. Otherwise convert
your fresh job:

```bash
# Insights-only path
cp traces/world-v2/baseline-eval/insights.jsonl \
  .runs/baseline-development-insights.jsonl

# Full path: replace the copy above with this conversion
python3 scripts/convert_atif_for_insights.py \
  .runs/harbor/baseline-development \
  --output .runs/baseline-development-insights.jsonl
```

Install and run Trace Analyst. The repository config enables trajectory patterns,
tool issues, and evaluation-linked failure patterns; it disables streams that need
user sentiment or an ethos-specific comparison:

```bash
uv tool install \
  'insight-agent @ git+https://github.com/NVIDIA-NeMo/labs-trace-intel.git@3a06bce1298190cd143a96880d6999052086632d'

export INSIGHT_AGENT_API_KEY="$NVIDIA_API_KEY"
insight-agent --config configs/trace-analyst.yaml \
  --trace.filesystem.path .runs/baseline-development-insights.jsonl
sed -n '1,220p' .runs/baseline-insights.yml
```

The output is a YAML list of problems with supporting trace IDs. The reference run
produced two recurring insights: required chat and domain tools were absent from the
baseline's directly presented catalog, and the agent did not reliably reach them
through Hermes' MCP discovery path. Several trials therefore answered without the
required evidence; another made 29 calls while searching for a support tool.

Inspect every cited trace before adopting the suggested fix literally. In this
runtime the MCP tools do exist, so adding a second copy of every schema is not the
only answer. The candidate instead makes the discovery route salient, removes
irrelevant built-ins, and bounds retries and calls. That interpretation is the
human engineering step between an insight and an arm.

Trace Analyst can also inspect the 36 unscored source traces for tool anomalies and
trajectory patterns. Evaluated rollouts are the primary input here because the
`eval_failure_patterns` stream can use the Harbor rewards.

## 7. Turn the findings into a candidate arm

An *arm* is one version of the agent harness under test. Both arms use the same
model, task prompt, MCP server, fixture, and verifier. Only these Hermes controls
change:

| Control | Baseline | Candidate |
| --- | --- | --- |
| System policy | `profiles/baseline-soul.md` | `profiles/candidate-soul.md` |
| Built-in toolsets | broad `hermes-cli` surface | `skills` only; task MCP remains available |
| Maximum turns | 60 | 12 |

Read the actual intervention:

```bash
diff -u profiles/baseline-soul.md profiles/candidate-soul.md || true
sed -n '1,90p' harbor_agents/hermes_flywheel.py
```

The candidate adds claim-to-source routing, search-then-read, evidence-completeness
checking, schema-first bounded JSON reads, one exact retry then one fallback,
connector-status handling, and prepare-without-send. Tool downsampling removes
irrelevant local/web/code paths, and the shorter turn cap bounds runaway behavior.

Nothing is hidden in a configurator. Edit the Markdown profile and the `ARM_CONFIG`
entry in `harbor_agents/hermes_flywheel.py` to create another arm. Add its name to
the `--arm` choices in `scripts/run_harbor_eval.py`. Change one coherent hypothesis
at a time, keep tasks and verifiers frozen, and use the Relay output to explain the
result.

## 8. Run the development A/B

Run the candidate on the same six tasks:

```bash
python3 scripts/run_harbor_eval.py \
  --arm candidate --split development --attempts 1 --concurrency 2 \
  --harbor .harbor-venv/bin/harbor --job-name candidate-development

python3 scripts/summarize_harbor_job.py \
  .runs/harbor/candidate-development \
  --output .runs/harbor/candidate-development-summary.json

jq -s 'map({job_dir, passed: .counts.passed, trials: .counts.total,
  pass_rate: .mean_reward, tool_calls: .tool_calls.total,
  exceptions: .counts.exceptions})' \
  .runs/harbor/{baseline,candidate}-development-summary.json
```

The reference smoke comparison is baseline `1/6` versus candidate `6/6`, with mean
tool calls falling from 5.00 to 2.17. For a stronger development estimate, rerun
*both* arms with fresh job names and `--attempts 3`; never add attempts only to the
arm or task that missed.

The Harbor reward is the authoritative score. Relay trajectories and Trace Analyst
explain behavior; they are not a second scorer. Confirm the summary's model,
provider, Hermes version, attempts, and exception policy match between arms.

## 9. Freeze the candidate and open the held-out set

Held-out tasks test whether the harness generalizes beyond the six development
cases. Do not inspect or tune against them until the candidate is frozen.

```bash
python3 scripts/run_harbor_eval.py \
  --arm baseline --split held-out --attempts 3 --concurrency 2 \
  --harbor .harbor-venv/bin/harbor --job-name baseline-held-out
python3 scripts/run_harbor_eval.py \
  --arm candidate --split held-out --attempts 3 --concurrency 2 \
  --harbor .harbor-venv/bin/harbor --job-name candidate-held-out

for arm in baseline candidate; do
  python3 scripts/summarize_harbor_job.py \
    ".runs/harbor/$arm-held-out" \
    --output ".runs/harbor/$arm-held-out-summary.json"
done
jq -s 'map({job_dir, passed: .counts.passed, trials: .counts.total,
  pass_rate: .mean_reward, tool_calls: .tool_calls.total,
  exceptions: .counts.exceptions})' \
  .runs/harbor/{baseline,candidate}-held-out-summary.json
```

The measured reference result is baseline `2/12` and candidate `11/12`. One
candidate miss still failed search-then-read, a useful reminder that a profile is a
probabilistic intervention rather than a guarantee. Keep timeouts and clean
zero-reward trials in the denominator and report the small sample size.

## Bring this workflow to your agent

Replace components at their contract boundaries:

- export your deployment traces as Relay-compatible ATIF;
- let Codex and Eval Author propose tasks from observed behavior, then complete the
  human privacy, access, meaning, and publication reviews;
- provide an isolated test implementation of your real tool schemas and state;
- adapt `HermesFlywheel` only if your agent needs different startup or profile
  plumbing; and
- preserve identical models, tasks, tools, and verifiers across harness arms.

Harbor is appropriate for isolated executable evals and A/B testing. When you need
large-scale rollouts, interactive environment lifecycles, or model/harness RL, use
the same fixture, dispatcher, and verifier contracts to build a NeMo Gym. See the
[Gym extension](gym-extension.md) for parity gates and division of responsibility.

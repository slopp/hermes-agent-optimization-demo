# Trace-to-harness flywheel

This is the canonical guide. It starts with a checked-in pile of Hermes traces,
uses Insights and Eval Author to turn observed failures into an eval, compares
two harness arms in Harbor, and checks the winning arm on held-out tasks. NeMo
Platform is not required.

## Choose a path

| Path | Use it when | Run |
| --- | --- | --- |
| Insights only | Inspect trace analysis without running an agent | Setup, 1, 2 |
| Reproduce the A/B | Run the shortest complete optimization loop | Setup, 1, 3, 4, 5, 6 |
| Re-author the eval | Apply Eval Author to your own trace pile | Setup, 1, 2, 3, then the Codex workflow |
| Recollect traces | Deploy Hermes through NemoClaw/OpenShell | Optional NemoClaw section |

The checked-in Eval Author reference tasks make the A/B independent of the
authoring path. Human review is required when creating or publishing a new
eval, not when running these reference tasks.

## Setup

Use a fresh Ubuntu 24.04 machine with native Docker, at least 4 vCPUs, 16 GB
RAM, and 50 GB free disk. The reference run completed on a 4-vCPU Brev CPU
instance; 8 vCPUs are recommended to reduce concurrent Harbor runtime.
Harbor 0.22.0's isolated verifier jobs require a Linux kernel with
`CONFIG_NFT_FIB_INET`; Docker Desktop's LinuxKit VM does not provide it. On
macOS, use a Colima Docker context or run this part on Linux.

Install the host tools on Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y binutils ca-certificates curl gh git jq make openssl
if ! command -v docker >/dev/null; then
  sudo apt-get install -y docker.io
fi
sudo usermod -aG docker "$USER"
newgrp docker
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
docker info >/dev/null
```

Clone and validate the tutorial:

```bash
git clone https://github.com/slopp/hermes-agent-optimization-demo.git
cd hermes-agent-optimization-demo
make test
make validate
```

Create Harbor's isolated environment. Keep the tested 0.22.0 pin: Eval Author
proof receipts and task schemas are version-sensitive.

The first task image build can take 10–20 minutes. With the image cached, the
one-attempt development and held-out smoke runs took about 20 minutes total on
the reference CPU host; three attempts per task can take 45–90 minutes and use
substantially more inference quota.

```bash
uv venv .harbor-venv --python 3.12
uv pip install --python .harbor-venv/bin/python 'harbor==0.22.0'
.harbor-venv/bin/harbor --version
```

When a model run is needed, enter an NVIDIA Build key at a masked prompt. The
key is forwarded to the allowlisted inference endpoint and is never baked into
the task image or written to the repository.

```bash
printf 'NVIDIA Build API key: '
read -rs NVIDIA_API_KEY
printf '\n'
export NVIDIA_API_KEY
```

## 1. Understand the starting point

**Purpose:** establish the inputs before optimization.

**Input:** 36 Relay-compatible ATIF traces in `traces/world-v2/corpus/`: six
independent trials for each of six behavior families. They were produced by
Hermes against the deterministic 504-record Northstar MCP world.

**Output:** a validated pile of traces. The pile is evidence to inspect, not
already an eval set.

```bash
jq '{traces: (.traces | length), groups: ([.traces[].logical_case_id] | group_by(.) | map({key: .[0], value: length}) | from_entries)}' \
  traces/world-v2/corpus/index.json
find traces/world-v2/corpus -name '*.atif.json' | wc -l
make validate
```

The six families cover multi-source evidence, search-then-read, bounded retry,
connector authentication, prepare-without-send, and bounded structured-file
inspection. Six development tasks were selected from these recurring shapes;
four differently worded cases are held out for the final gate. `--attempts 3`
means three model trials per task: 18 development trials and 12 held-out trials
per arm. The quick path below uses one attempt first to control cost.

## 2. Analyze the trace pile with Insights

**Purpose:** find repeated trajectory patterns and tool problems worth turning
into testable hypotheses.

**Input:** the 36 checked-in ATIF traces.

**Output:** deterministic evidence cards and clusters. These inform task
selection and harness changes; they do not score the later A/B.

**Skip:** skip this section only if you want to run the already-derived eval.

Access to the standalone Insights preview repository is required:

```bash
gh auth status || gh auth login --web --git-protocol https
python3 scripts/convert_atif_for_insights.py \
  traces/world-v2/corpus \
  --output .runs/insights/starting-corpus.jsonl

git clone https://github.com/NVIDIA/nemo-platform-insights-preview.git \
  ../nemo-platform-insights-preview
cd ../nemo-platform-insights-preview
git checkout 02c05644809acafe09be42501c8d4db23d268016
uv sync --locked

uv run insight-agent validate \
  --traces ../hermes-agent-optimization-demo/.runs/insights/starting-corpus.jsonl
uv run insight-agent coverage \
  ../hermes-agent-optimization-demo/.runs/insights/starting-corpus.jsonl \
  --with-findings
```

Run the full deterministic pipeline from the tutorial root:

```bash
cd ../hermes-agent-optimization-demo
export DEMO_ROOT="$PWD"
sed \
  -e "s#path: .*#path: $DEMO_ROOT/.runs/insights/starting-corpus.jsonl#" \
  -e "s#directory: .*#directory: $DEMO_ROOT/.runs/insights/starting-output#" \
  configs/insights-standalone.yaml > /tmp/hermes-insights.yaml

cd ../nemo-platform-insights-preview
uv run insight-agent --config /tmp/hermes-insights.yaml
cd ../hermes-agent-optimization-demo
```

Read the cards alongside their cited traces. In this world, useful signals are
incomplete enterprise evidence, search hits used without a subsequent read,
repeated or modified retries, invalid structured-read arguments, and irrelevant
local/web detours. Treat each as a hypothesis until an eval isolates it.

### Optional: use the LLM Analyst

The deterministic pipeline above needs no model. To ask Nemotron to synthesize
its findings, enable the Analyst only after the A/B or with separate quota:

```bash
cd ../nemo-platform-insights-preview
export INSIGHT_AGENT_API_KEY="$NVIDIA_API_KEY"
uv run insight-agent run-analyst \
  ../hermes-agent-optimization-demo/.runs/insights/starting-corpus.jsonl \
  -o ../hermes-agent-optimization-demo/.runs/insights/analyst \
  --model openai/nvidia/nemotron-3-ultra-550b-a55b \
  --api-base https://integrate.api.nvidia.com/v1
cd ../hermes-agent-optimization-demo
```

## 3. Understand or re-author the Eval Author tasks

**Purpose:** turn trace evidence into portable tasks with explicit tool access,
isolated verifiers, and control proofs.

**Input:** the trace pile, `ETHOS.md`, and the Insights hypotheses.

**Output:** six development Harbor tasks. Each runs the real fixture-backed
`enterprise-world` MCP surface and grades the answer, actual MCP call log,
retry/call budget, and mutation state.

**Skip:** the tasks under `evals/harbor-tasks-v2/` are checked in. Skip task
authoring when your goal is to reproduce the A/B.

Eval Author is a collection of skills for a coding agent, not a prompt-mining
CLI. The coding agent inspects and clusters the trace pile, proposes the finite
behavior denominator, selects representative traces, and applies the skills one
trace at a time. A person reviews privacy, tool access, task meaning, and final
publication artifacts. That review is an attestation about what a task may
contain and access; it should never be replaced by editing a JSON status field.

Install the source skills and the [Codex CLI](https://developers.openai.com/codex/cli):

```bash
git clone https://github.com/NVIDIA-NeMo/nemo-platform.git ../nemo-platform
git -C ../nemo-platform checkout a0bb79bbfa122063c7fcdff824a94e46220efc37
curl -fsSL https://chatgpt.com/codex/install.sh | sh
codex
```

At the Codex prompt, paste `prompts/eval-author-from-traces.md`. It directs
Codex to read the definitive Eval Author skills, audit all 36 traces, select
representatives, and stop at every human review gate. Resume Codex after each
review. Working artifacts remain under `.eval-author/`; reviewed exports can be
compared with `evals/harbor-tasks-v2/`.

The important access decision is `real`, not `none`: the task starts the same
task-local MCP server the evaluated Hermes agent uses. The server is synthetic,
but the agent must discover and call it through MCP. A frozen
`enterprise-query` shortcut would test answer lookup rather than the harness
behavior under optimization.

The reference tasks make that mechanism inspectable:

```bash
sed -n '1,180p' evals/harbor-tasks-v2/source-coverage/task.toml
sed -n '1,220p' evals/harbor-tasks-v2/source-coverage/tests/verify.py

python3 scripts/materialize_harbor_tasks.py \
  --output .runs/reference-task-rebuild
diff -qr -x __pycache__ -x '*.pyc' \
  evals/harbor-tasks-v2 .runs/reference-task-rebuild
```

Before trusting a new task, require NOP failure, Oracle success, a relevant
negative control, MCP registration/discovery/invocation evidence, and a separate
no-network verifier. The checked-in set passed NOP and Oracle controls for all
ten tasks on the tested Linux host.

## 4. Run the development A/B in Harbor

**Purpose:** test a harness hypothesis while holding the model, prompts, world,
MCP tools, and verifiers fixed.

**Input:** six development tasks and two Hermes harness arms.

**Output:** authoritative Harbor rewards plus Relay ATOF/ATIF for every trial.

**Skip:** do not skip this section in the complete optimization loop.

Run a one-attempt smoke comparison:

```bash
python3 scripts/run_harbor_eval.py \
  --arm baseline --split development --attempts 1 --concurrency 2 \
  --harbor .harbor-venv/bin/harbor --job-name baseline-development

python3 scripts/run_harbor_eval.py \
  --arm candidate-v4 --split development --attempts 1 --concurrency 2 \
  --harbor .harbor-venv/bin/harbor --job-name candidate-development

python3 scripts/summarize_harbor_job.py \
  .runs/harbor/baseline-development \
  --output .runs/harbor/baseline-development-summary.json
python3 scripts/summarize_harbor_job.py \
  .runs/harbor/candidate-development \
  --output .runs/harbor/candidate-development-summary.json
```

For a measured result, rerun both arms with fresh job names and
`--attempts 3`. Do not overwrite or selectively discard trials. A trial with a
clean runner exit but a zero verifier reward is an agent failure, not an
infrastructure exclusion.

Harbor's verifier reward is the score. Insights traces explain the behavior but
do not substitute a second scorer. The summary's `runtime` object records the
Hermes version and resolved provider/model; require those fields to match across
arms.

## 5. Inspect and adjust the harness change

**Purpose:** connect trace evidence to a concrete, editable intervention.

**Input:** baseline task failures, Relay traces, and Insights findings.

**Output:** a candidate profile that can be tested without changing the task.

The arms are defined in `harbor_agents/hermes_flywheel.py`:

| Arm | Hermes profile | Built-in toolsets | Turn cap |
| --- | --- | --- | ---: |
| baseline | `profiles/nemoclaw-baseline-soul.md` | broad `hermes-cli` surface | 60 |
| candidate-v4 | `profiles/nemoclaw-candidate-v4-soul.md` | skills only; MCP remains available | 12 |

The candidate profile applies several emergent patterns:

- claim-to-source routing and an evidence-completeness stop check;
- search-then-read before citing chat or mail evidence;
- one identical retry followed by one declared fallback;
- schema inspection before a bounded `/evidence` JSON read;
- connector-status awareness rather than invented CRM data;
- prepare-without-send for approval-gated actions; and
- irrelevant-tool downsampling plus a smaller turn budget.

Nothing is hidden in a configurator: edit the Markdown profile, `toolsets`, or
`max_turns` mapping directly. Keep task inputs and verifiers untouched while
iterating. These policies are examples to test against your traces, not generic
rules to paste into every agent.

Convert Harbor Relay artifacts and run another Insights pass when you need to
understand a score:

```bash
python3 scripts/convert_atif_for_insights.py \
  .runs/harbor/baseline-development \
  --output .runs/harbor/baseline-development-insights.jsonl
python3 scripts/convert_atif_for_insights.py \
  .runs/harbor/candidate-development \
  --output .runs/harbor/candidate-development-insights.jsonl
```

## 6. Open the held-out gate

**Purpose:** test whether the harness change generalizes beyond the six cases
used during development.

**Input:** the frozen candidate and four held-out paraphrases.

**Output:** baseline-versus-candidate rewards on unseen task wording.

**Skip:** skip only during iteration; a result is not ready to claim without
this gate.

```bash
python3 scripts/run_harbor_eval.py \
  --arm baseline --split held-out --attempts 3 --concurrency 2 \
  --harbor .harbor-venv/bin/harbor --job-name baseline-held-out

python3 scripts/run_harbor_eval.py \
  --arm candidate-v4 --split held-out --attempts 3 --concurrency 2 \
  --harbor .harbor-venv/bin/harbor --job-name candidate-held-out

python3 scripts/summarize_harbor_job.py \
  .runs/harbor/baseline-held-out \
  --output .runs/harbor/baseline-held-out-summary.json
python3 scripts/summarize_harbor_job.py \
  .runs/harbor/candidate-held-out \
  --output .runs/harbor/candidate-held-out-summary.json
```

The summarizer writes the available result and exits nonzero when a trial has an
exception. A timeout from an overlong agent trajectory is a measured harness
failure; inspect it and keep it in the denominator rather than rerunning only
that trial.

Compare pass rate, exceptions, call counts, forbidden mutations, and cited
failure reasons. Keep baseline and candidate model IDs, attempt counts, and
infrastructure identical. The measured reference run is in `docs/results.md`.

## Optional: deploy and recollect with NemoClaw

This path demonstrates that the same profiles and MCP world can run in a
deployed OpenShell sandbox. It is not required for Insights, Eval Author, or
the Harbor A/B.

Install the HTTPS tunnel dependency on Ubuntu:

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | \
  sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" | \
  sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update
sudo apt-get install -y cloudflared
```

Install and onboard the tested Hermes integration:

```bash
curl -fsSL https://www.nvidia.com/nemoclaw.sh | \
  NEMOCLAW_AGENT=hermes bash -s -- --defer-onboarding

export DEMO_SANDBOX=hermes-demo
nemoclaw onboard --agent hermes --name "$DEMO_SANDBOX"
nemoclaw "$DEMO_SANDBOX" status
export DEMO_GATEWAY="$(openshell gateway list --output json | \
  jq -r '.[] | select(.active) | .name')"
test -n "$DEMO_GATEWAY"
```

Choose NVIDIA Build, `nvidia/nemotron-3-ultra-550b-a55b`, `No profile
(OpenShell defaults)`, and Balanced policies in the masked onboarding prompts. Sandbox names
are limited to 19 characters. If onboarding stopped after a recoverable check:

```bash
nemoclaw onboard --resume --agent hermes --name "$DEMO_SANDBOX"
```

On a fresh host with UFW enabled, the gateway preflight may print a bridge- and
address-specific `ufw allow` command for port 8080. Run that exact generated
command, then use the resume command above; do not copy a rule from another
host.

Build and expose the deterministic MCP server:

```bash
docker build -f deploy/mock-mcp/Dockerfile -t enterprise-world-mcp:local .
export PA_STYLE_MOCK_MCP_TOKEN="$(openssl rand -hex 24)"
docker run --detach --rm --name enterprise-world-mcp \
  -p 127.0.0.1:8000:8000 \
  -e PA_STYLE_MOCK_MCP_TOKEN="$PA_STYLE_MOCK_MCP_TOKEN" \
  enterprise-world-mcp:local --fixture /app/fixtures/world-v2.json

mkdir -p .runs/runtime
python3 scripts/ensure_nemoclaw_mcp.py \
  --sandbox "$DEMO_SANDBOX" --runtime-dir .runs/runtime
nemoclaw "$DEMO_SANDBOX" mcp status enterprise-world --tools
```

Apply either arm and collect more Relay traces:

```bash
python3 scripts/configure_nemoclaw_arm.py \
  --gateway "$DEMO_GATEWAY" --sandbox "$DEMO_SANDBOX" \
  --arm baseline --trace-label world-v2-baseline-repro

python3 scripts/run_nemoclaw_matrix.py \
  --gateway "$DEMO_GATEWAY" --sandbox "$DEMO_SANDBOX" \
  --matrix experiments/fidelity-matrix-v2.json \
  --arm baseline --trials 3 --ensure-mock-mcp \
  --mcp-runtime-dir .runs/runtime --reset-demo-sessions \
  --output .runs/nemoclaw/baseline/responses
```

`configure_nemoclaw_arm.py` is optional convenience. To apply the change
yourself, upload the chosen profile to `/sandbox/.hermes/SOUL.md`, set
`agent.max_turns` with `hermes config set`, enable or disable the toolsets shown
in the table above, and install `configs/nemoclaw-relay-plugins.toml` at the path
named by `HERMES_NEMO_RELAY_PLUGINS_TOML`. The helper performs only those
operations; inspect it before using it on a non-disposable sandbox.

The runtime helper uses an ephemeral HTTPS tunnel. For repeatable team use,
deploy the same container behind stable HTTPS. Stop the tutorial server when
finished:

```bash
kill "$(cat .runs/runtime/cloudflared.pid)"
docker stop enterprise-world-mcp
```

## Where NeMo Gym begins

This loop optimizes a harness from trace evidence. Move the same world, tools,
and verifier into NeMo Gym when you need rollout-scale benchmarking or
model/harness reinforcement learning. See `docs/gym-extension.md` for the
parity gates.

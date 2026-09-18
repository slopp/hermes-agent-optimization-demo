# End-to-end walkthrough

This is the canonical path through the demo. It uses NVIDIA Build, a
NemoClaw-managed Hermes sandbox, Relay, local Eval Author, and standalone
Insights. NeMo Platform is not required.

The checked-in traces let you start at section 4. Sections 1–3 show how to
recreate them.

## 1. Clone and validate

Requirements are Git, Make, Python 3.11+, `uv`, Docker, `curl`, `openssl`, `jq`, and
`cloudflared` (or another HTTPS ingress). Step 6 has one additional constraint:
Harbor 0.22.0 needs a Docker daemon whose Linux kernel supports nftables
`CONFIG_NFT_FIB_INET`. Native Linux normally does. Docker Desktop's LinuxKit
kernel does not; on macOS, use Colima for the Harbor proofs.

```bash
git clone https://github.com/slopp/hermes-agent-optimization-demo.git
cd hermes-agent-optimization-demo

command -v git make python3 uv docker curl openssl jq cloudflared
docker info >/dev/null
make test
make validate
make mock-mcp-container-check
```

On Ubuntu or Debian, install missing `uv` and `cloudflared` first:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | \
  sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" | \
  sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update
sudo apt-get install -y make cloudflared
```

On macOS:

```bash
brew install uv cloudflared jq
```

On macOS, also prepare the compatible Docker context that Step 6 will use:

```bash
brew install colima
colima start --cpu 6 --memory 12 --disk 100
docker --context colima info >/dev/null
```

Docker Desktop can remain the default context for the other sections.

## 2. Provision Hermes with NemoClaw

Install NemoClaw with Hermes selected, then run the onboarding wizard:

```bash
curl -fsSL https://www.nvidia.com/nemoclaw.sh | \
  NEMOCLAW_AGENT=hermes bash -s -- --defer-onboarding

export DEMO_SANDBOX=hermes-demo
nemoclaw onboard --agent hermes --name "$DEMO_SANDBOX"
nemoclaw "$DEMO_SANDBOX" status
openshell gateway list
export DEMO_GATEWAY="$(openshell gateway list --output json | jq -r '.[] | select(.active) | .name')"
test -n "$DEMO_GATEWAY"
```

Choose the NVIDIA provider, `nvidia/nemotron-3-ultra-550b-a55b`, the default
resource profile, and the Balanced policy presets in the wizard. Enter the
NVIDIA Build key only at its masked credential prompt; do not put it in this
repository or the command line. This walkthrough was verified with NemoClaw
v0.0.124. If onboarding stops after a recoverable preflight failure:

```bash
nemoclaw onboard --resume
```

Sandbox names are limited to 19 characters. If a previous attempt left this
disposable tutorial sandbox in a not-ready state and its automatic backup also
fails, discard only that known demo sandbox and start the wizard again:

```bash
nemoclaw "$DEMO_SANDBOX" destroy --yes --no-cleanup-gateway
nemoclaw onboard --agent hermes --name "$DEMO_SANDBOX" --fresh
```

Do not use this recovery for a sandbox containing state you need to preserve.

NemoClaw creates the OpenShell gateway, isolated sandbox, inference route, and
Hermes runtime. `nemoclaw "$DEMO_SANDBOX" status` is the authoritative
readiness check.

## 3. Serve and register the fictional MCP

Build the 504-record world-v2 server, create an ephemeral bearer token, and run
it in the background:

```bash
docker build -f deploy/mock-mcp/Dockerfile \
  -t enterprise-world-mcp:local .

export PA_STYLE_MOCK_MCP_TOKEN="$(openssl rand -hex 24)"

docker run --detach --rm --name enterprise-world-mcp \
  -p 127.0.0.1:8000:8000 \
  -e PA_STYLE_MOCK_MCP_TOKEN="$PA_STYLE_MOCK_MCP_TOKEN" \
  enterprise-world-mcp:local \
  --fixture /app/fixtures/world-v2.json
```

Expose loopback through HTTPS and extract the temporary URL:

```bash
export DEMO_RUNTIME="$(mktemp -d)"
cloudflared tunnel --url http://127.0.0.1:8000 \
  >"$DEMO_RUNTIME/cloudflared.log" 2>&1 &
export CLOUDFLARED_PID=$!

for attempt in 1 2 3 4 5 6 7 8 9 10; do
  ENTERPRISE_MCP_URL="$(sed -n 's#.*\(https://[a-z0-9-]*\.trycloudflare\.com\).*#\1#p' \
    "$DEMO_RUNTIME/cloudflared.log" | head -1)"
  test -n "$ENTERPRISE_MCP_URL" && break
  sleep 1
done
export ENTERPRISE_MCP_URL
test -n "$ENTERPRISE_MCP_URL"
printf '%s\n' "$ENTERPRISE_MCP_URL"

nemoclaw "$DEMO_SANDBOX" mcp add enterprise-world \
  --url "$ENTERPRISE_MCP_URL/mcp" \
  --env PA_STYLE_MOCK_MCP_TOKEN
nemoclaw "$DEMO_SANDBOX" mcp list
nemoclaw "$DEMO_SANDBOX" mcp status enterprise-world --tools
```

A quick tunnel changes each time it restarts; re-run `mcp add` with the new
URL. For repeatable team use, deploy this image behind stable HTTPS. If an MCP
probe succeeds on the host but Hermes receives `403`, recreate the tunnel and
registration so OpenShell pins the endpoint's current IPv4 and IPv6 addresses.

After the tutorial:

```bash
kill "$CLOUDFLARED_PID"
docker stop enterprise-world-mcp
```

## 4. Inspect the starting artifacts

No model call is needed:

```bash
python3 scripts/validate_trace_manifest.py traces/world-v2/manifest.json
python3 scripts/validate_trace_derived_suite.py evals/flywheel-eval-set-v2.json
python3 scripts/validate_eval_author_products.py evals/flywheel-eval-set-v2.json
```

The bundle contains six baseline ATIF traces, a 10-case suite (six
trace-derived development cases plus four held-outs), and six technically
proved Eval Author products. Publication status remains pending human review.

## 5. Collect baseline traces with Relay

An arm is a versioned harness configuration: system policy, visible built-in
tools, turn budget, and Relay output label. The baseline intentionally exposes
the broad Hermes toolset and allows 60 turns.

Install it directly so every mutation is visible:

```bash
export DEMO_SANDBOX=hermes-demo
export TRACE_LABEL=world-v2-baseline-repro

openshell sandbox upload "$DEMO_SANDBOX" \
  profiles/nemoclaw-baseline-soul.md /sandbox
openshell sandbox exec -n "$DEMO_SANDBOX" --no-tty -- \
  mv /sandbox/nemoclaw-baseline-soul.md /sandbox/.hermes/SOUL.md
openshell sandbox exec -n "$DEMO_SANDBOX" --no-tty -- \
  hermes config set agent.max_turns 60
openshell sandbox exec -n "$DEMO_SANDBOX" --no-tty -- \
  hermes tools enable --platform cli \
  web browser terminal file code_execution vision image_gen tts skills todo \
  memory session_search clarify delegation cronjob computer_use audio nemoclaw

sed "s/replace-me/$TRACE_LABEL/g" configs/nemoclaw-relay-plugins.toml \
  > /tmp/relay-plugins.toml
openshell sandbox upload "$DEMO_SANDBOX" /tmp/relay-plugins.toml /sandbox
openshell sandbox exec -n "$DEMO_SANDBOX" --no-tty -- \
  mkdir -p /sandbox/.hermes/nemo-relay
openshell sandbox exec -n "$DEMO_SANDBOX" --no-tty -- \
  mv /sandbox/relay-plugins.toml \
  /sandbox/.hermes/nemo-relay/relay-plugins.toml
openshell sandbox exec -n "$DEMO_SANDBOX" --no-tty -- \
  cp /sandbox/.hermes/nemo-relay/relay-plugins.toml \
  /sandbox/.hermes/nemo-relay/nemoclaw-relay-plugins.toml
openshell sandbox exec -n "$DEMO_SANDBOX" --no-tty -- sh -c \
  "grep -q '^HERMES_NEMO_RELAY_PLUGINS_TOML=' /sandbox/.hermes/.env 2>/dev/null \
  || echo HERMES_NEMO_RELAY_PLUGINS_TOML=/sandbox/.hermes/nemo-relay/relay-plugins.toml \
  >>/sandbox/.hermes/.env"
```

Hermes owns Relay directly and reads its exporter config only from the file named
by `HERMES_NEMO_RELAY_PLUGINS_TOML`. Nothing creates `/sandbox/.hermes/nemo-relay`
for you, and without the variable the arm runs but writes no ATOF or ATIF.

The equivalent convenience command is:

```bash
python3 scripts/configure_nemoclaw_arm.py \
  --gateway "$DEMO_GATEWAY" \
  --sandbox "$DEMO_SANDBOX" --arm baseline --trace-label "$TRACE_LABEL"
```

Run three development trials. `--reset-demo-sessions` deletes Hermes session
history, so use it only with this disposable sandbox. Refresh and verify the
MCP bridge immediately before a batch; quick-tunnel DNS can change while the
sandbox's egress policy remains pinned.

```bash
nemoclaw "$DEMO_SANDBOX" mcp add enterprise-world \
  --url "$ENTERPRISE_MCP_URL/mcp" \
  --env PA_STYLE_MOCK_MCP_TOKEN
nemoclaw "$DEMO_SANDBOX" mcp status enterprise-world --tools

python3 scripts/run_nemoclaw_matrix.py \
  --sandbox "$DEMO_SANDBOX" \
  --gateway "$DEMO_GATEWAY" \
  --matrix experiments/fidelity-matrix-v2.json \
  --arm baseline --trials 3 --delay-seconds 30 \
  --retries 3 --retry-backoff-seconds 180 \
  --reset-demo-sessions \
  --output .runs/world-v2/baseline-dev/responses
```

Download Relay ATOF and convert it:

```bash
mkdir -p .runs/world-v2/baseline-dev/relay
openshell sandbox download "$DEMO_SANDBOX" \
  "/sandbox/hermes-flywheel-traces/$TRACE_LABEL/atof/events.jsonl" \
  .runs/world-v2/baseline-dev/relay

python3 scripts/convert_atof_to_atif.py \
  --atof .runs/world-v2/baseline-dev/relay/events.jsonl \
  --output-dir .runs/world-v2/baseline-dev/atif
python3 scripts/convert_atof_for_insights.py \
  --atof .runs/world-v2/baseline-dev/relay/events.jsonl \
  --matrix experiments/fidelity-matrix-v2.json \
  --output .runs/world-v2/baseline-dev/insights.jsonl
```

Inspect Relay's requested and returned model IDs. Treat the returned ID as
authoritative.

## 6. Derive the eval with Eval Author

Clone only the source tree that contains Eval Author; no Platform service is
started:

```bash
git clone https://github.com/NVIDIA-NeMo/nemo-platform.git ../nemo-platform
cd ../nemo-platform
git checkout a0bb79bbfa122063c7fcdff824a94e46220efc37
uv venv .venv --python 3.12
cd ../hermes-agent-optimization-demo

export EA_REPO="$(cd ../nemo-platform && pwd)"
export EA_PY="$EA_REPO/.venv/bin/python"
export EA="$EA_REPO/plugins/nemo-eval-author/skills/eval-author-trace-environment/scripts/trace_environment.py"
export EA_ROOT="$PWD/.eval-author/world-v2-trace-environments"

"$EA_PY" "$EA" batch-prepare \
  --root "$EA_ROOT" --manifest traces/world-v2/eval-author-batch.json
"$EA_PY" "$EA" batch-status \
  --root "$EA_ROOT" --manifest traces/world-v2/eval-author-batch.json
```

Open every `safe/trace.atif.json` and `private/privacy-audit.json`. After
reviewing all strings and findings, record each review:

```bash
for CASE in source-coverage read-after-search bounded-retry auth-awareness \
  approval-boundary bounded-structured-inspection; do
  "$EA_PY" "$EA" review-privacy \
    --task-dir "$EA_ROOT/$CASE" --reviewer-kind human \
    --note "Reviewed every safe string and privacy-audit finding."
done

python3 scripts/materialize_eval_author_tasks.py \
  --task-root "$EA_ROOT" --world fixtures/world-v2.json
```

The source traces contain tool calls, while each portable candidate deliberately
uses the frozen world snapshot through `enterprise-query` and needs no live or
replayed source tool. Inventory those calls, inspect the generated plans, and
record `none` for every source-tool surface before proving the candidates:

```bash
for CASE in source-coverage read-after-search bounded-retry auth-awareness \
  approval-boundary bounded-structured-inspection; do
  "$EA_PY" "$EA" inventory-tool-calls --task-dir "$EA_ROOT/$CASE"
  "$EA_PY" "$EA" plan-tool-call-access --task-dir "$EA_ROOT/$CASE"
  python3 scripts/prepare_eval_author_tool_access.py \
    --task-dir "$EA_ROOT/$CASE"

  jq . "$EA_ROOT/$CASE/private/tool-call-plan.json"
  jq . "$EA_ROOT/$CASE/private/tool-access-decisions.json"

  "$EA_PY" "$EA" resolve-tool-call-access \
    --task-dir "$EA_ROOT/$CASE" \
    --decisions "$EA_ROOT/$CASE/private/tool-access-decisions.json" \
    --reviewer-kind human
done
```

Do not select `none` for a task that actually needs a live integration or mock
replay. In that case, author and review the corresponding `real` or `mock`
decision and provide the required adapter instead.

Install Harbor in a separate environment, then prove every candidate:

```bash
uv venv .harbor-venv --python 3.12
uv pip install --python .harbor-venv/bin/python 'harbor==0.22.0'

if [ "$(uname -s)" = Darwin ]; then
  export HARBOR_DOCKER_CONTEXT=colima
else
  export HARBOR_DOCKER_CONTEXT=default
fi

python3 scripts/prove_eval_author_tasks.py \
  --task-root "$EA_ROOT" \
  --case source-coverage \
  --case read-after-search \
  --case bounded-retry \
  --case auth-awareness \
  --case approval-boundary \
  --case bounded-structured-inspection \
  --helper "$EA" \
  --harbor-python "$PWD/.harbor-venv/bin/python" \
  --harbor "$PWD/.harbor-venv/bin/harbor" \
  --docker-context "$HARBOR_DOCKER_CONTEXT"
```

Each proof runs two NOPs, two Oracles, and one incomplete-answer control with a
separate no-network verifier. The runner creates the shared `private/jobs`
directory and performs Harbor's kernel-capability probe before writing any run
receipts. If it rejects Docker Desktop, switching only the selected context to
Colima is the expected macOS workaround. Do not change `network_mode` to
`public`: the isolation is part of the Eval Author proof contract. Harbor's
static no-network
[Docker Desktop limitation](https://github.com/harbor-framework/harbor/issues/2593)
remains open upstream, so upgrading past this tutorial's tested pin is not
currently a fix. Use Eval Author's
`prepare-publication`, `review-publication`, and `export` commands only
after inspecting their exact previews. The checked-in exports show the expected
result under `evals/eval-author-products-v2`.

With all technical proofs passing, `batch-status` reports
`candidate_unproven` until a human records the privacy, tool-access, and
publication reviews. That status is expected during an automated or
agent-assisted walkthrough; do not mislabel an agent review as human.

## 7. Analyze with standalone Insights

The standalone Insight Agent repository is currently an access-controlled
preview. Obtain repository access and authenticate GitHub before continuing;
this is the only non-public source dependency in the walkthrough.

```bash
gh auth status
git clone https://github.com/NVIDIA/nemo-platform-insights-preview.git \
  ../nemo-platform-insights-preview
cd ../nemo-platform-insights-preview
git checkout 02c05644809acafe09be42501c8d4db23d268016
uv sync --locked

uv run insight-agent validate \
  --traces ../hermes-agent-optimization-demo/.runs/world-v2/baseline-dev/insights.jsonl
uv run insight-agent coverage \
  ../hermes-agent-optimization-demo/.runs/world-v2/baseline-dev/insights.jsonl \
  --with-findings
```

For the deterministic full pipeline, create an absolute-path config and run:

```bash
cd ../hermes-agent-optimization-demo
export DEMO_ROOT="$PWD"
sed -e "s#path: .*#path: $DEMO_ROOT/.runs/world-v2/baseline-dev/insights.jsonl#" \
  -e "s#directory: .*#directory: $DEMO_ROOT/.runs/world-v2/baseline-dev/insights-out#" \
  configs/insights-standalone.yaml > /tmp/insights-world-v2.yaml

cd ../nemo-platform-insights-preview
uv run insight-agent --config /tmp/insights-world-v2.yaml
```

Use `/tmp/insights-world-v2.yaml` in the final command. Review
`anomaly_and_patterns/digest.md`, `tool_issues/cards.md`, and cited traces
together. A finding is a hypothesis, not a fix. Run the optional LLM Analyst
after rollout collection in section 9 so it does not consume the same Build
quota immediately before the A/B test.

## 8. Apply the candidate arm

The baseline findings suggested enterprise-first routing and irrelevant-tool
downsampling. Candidate v3 improved markedly but world-v2 still exposed source
enumeration, modified retries, and guessed JSON arguments. Candidate v4 made
those transitions explicit.

Its direct Hermes changes are:

```bash
export TRACE_LABEL=world-v2-candidate-v4-repro
openshell sandbox upload "$DEMO_SANDBOX" \
  profiles/nemoclaw-candidate-v4-soul.md /sandbox
openshell sandbox exec -n "$DEMO_SANDBOX" --no-tty -- \
  mv /sandbox/nemoclaw-candidate-v4-soul.md /sandbox/.hermes/SOUL.md
openshell sandbox exec -n "$DEMO_SANDBOX" --no-tty -- \
  hermes config set agent.max_turns 12
openshell sandbox exec -n "$DEMO_SANDBOX" --no-tty -- \
  hermes tools disable --platform cli \
  web browser terminal file code_execution vision image_gen tts todo memory \
  session_search clarify delegation cronjob computer_use audio nemoclaw

sed "s/replace-me/$TRACE_LABEL/g" configs/nemoclaw-relay-plugins.toml \
  > /tmp/relay-plugins.toml
openshell sandbox upload "$DEMO_SANDBOX" /tmp/relay-plugins.toml /sandbox
openshell sandbox exec -n "$DEMO_SANDBOX" --no-tty -- \
  mkdir -p /sandbox/.hermes/nemo-relay
openshell sandbox exec -n "$DEMO_SANDBOX" --no-tty -- \
  mv /sandbox/relay-plugins.toml \
  /sandbox/.hermes/nemo-relay/relay-plugins.toml
openshell sandbox exec -n "$DEMO_SANDBOX" --no-tty -- \
  cp /sandbox/.hermes/nemo-relay/relay-plugins.toml \
  /sandbox/.hermes/nemo-relay/nemoclaw-relay-plugins.toml
```

`nemoclaw-candidate-v4-soul.md` is ordinary Hermes policy text: edit its
source routing, retry transition, JSON pointer, approval rule, or call budget
to test a different hypothesis. The helper merely performs these same uploads,
config writes, and tool toggles:

```bash
python3 scripts/configure_nemoclaw_arm.py \
  --gateway "$DEMO_GATEWAY" \
  --sandbox "$DEMO_SANDBOX" --arm candidate-v4 \
  --trace-label "$TRACE_LABEL"
```

Refresh the MCP bridge, run three candidate trials at a paced cadence, download
their distinct Relay stream, and convert it:

```bash
nemoclaw "$DEMO_SANDBOX" mcp add enterprise-world \
  --url "$ENTERPRISE_MCP_URL/mcp" \
  --env PA_STYLE_MOCK_MCP_TOKEN
nemoclaw "$DEMO_SANDBOX" mcp status enterprise-world --tools

python3 scripts/run_nemoclaw_matrix.py \
  --sandbox "$DEMO_SANDBOX" --gateway "$DEMO_GATEWAY" \
  --matrix experiments/fidelity-matrix-v2.json \
  --arm candidate --trials 3 --delay-seconds 30 \
  --retries 3 --retry-backoff-seconds 180 \
  --reset-demo-sessions \
  --output .runs/world-v2/candidate-v4-dev/responses

mkdir -p .runs/world-v2/candidate-v4-dev/relay
openshell sandbox download "$DEMO_SANDBOX" \
  "/sandbox/hermes-flywheel-traces/$TRACE_LABEL/atof/events.jsonl" \
  .runs/world-v2/candidate-v4-dev/relay
python3 scripts/convert_atof_for_insights.py \
  --atof .runs/world-v2/candidate-v4-dev/relay/events.jsonl \
  --matrix experiments/fidelity-matrix-v2.json \
  --output .runs/world-v2/candidate-v4-dev/insights.jsonl
```

The runner treats Hermes terminal messages such as exhausted 429 retries as
failures even when the CLI exits zero. It also catches host/runtime failures,
preserves each failed attempt, waits, and retries the same logical trial. If all
configured retries fail, wait for
the shared endpoint quota to recover and rerun only the affected scenario with
`--scenario CASE`; keep `--valid-only` when scoring. Then score:

```bash
python3 scripts/score_insights_traces.py --valid-only \
  --suite evals/flywheel-eval-set-v2.json \
  --arm baseline=.runs/world-v2/baseline-dev/insights.jsonl \
  --arm candidate-v4=.runs/world-v2/candidate-v4-dev/insights.jsonl \
  --output .runs/world-v2/development-ab.json
```

## 9. Run the held-out gate

Reconfigure and run both arms against
`experiments/held-out-matrix-v2.json`, keeping fixture, provider route, model,
trial count, and timeout fixed. Convert each ATOF file with the held-out matrix,
then score:

```bash
python3 scripts/configure_nemoclaw_arm.py \
  --gateway "$DEMO_GATEWAY" --sandbox "$DEMO_SANDBOX" \
  --arm baseline --trace-label world-v2-baseline-held-out
nemoclaw "$DEMO_SANDBOX" mcp add enterprise-world \
  --url "$ENTERPRISE_MCP_URL/mcp" --env PA_STYLE_MOCK_MCP_TOKEN
nemoclaw "$DEMO_SANDBOX" mcp status enterprise-world --tools
python3 scripts/run_nemoclaw_matrix.py \
  --gateway "$DEMO_GATEWAY" --sandbox "$DEMO_SANDBOX" \
  --matrix experiments/held-out-matrix-v2.json \
  --arm baseline --trials 3 --delay-seconds 30 \
  --retries 3 --retry-backoff-seconds 180 \
  --reset-demo-sessions \
  --output .runs/world-v2/baseline-held-out/responses

python3 scripts/configure_nemoclaw_arm.py \
  --gateway "$DEMO_GATEWAY" --sandbox "$DEMO_SANDBOX" \
  --arm candidate-v4 --trace-label world-v2-candidate-v4-held-out
nemoclaw "$DEMO_SANDBOX" mcp add enterprise-world \
  --url "$ENTERPRISE_MCP_URL/mcp" --env PA_STYLE_MOCK_MCP_TOKEN
nemoclaw "$DEMO_SANDBOX" mcp status enterprise-world --tools
python3 scripts/run_nemoclaw_matrix.py \
  --gateway "$DEMO_GATEWAY" --sandbox "$DEMO_SANDBOX" \
  --matrix experiments/held-out-matrix-v2.json \
  --arm candidate --trials 3 --delay-seconds 30 \
  --retries 3 --retry-backoff-seconds 180 \
  --reset-demo-sessions \
  --output .runs/world-v2/candidate-v4-held-out/responses

mkdir -p .runs/world-v2/baseline-held-out/relay \
  .runs/world-v2/candidate-v4-held-out/relay
openshell sandbox download "$DEMO_SANDBOX" \
  /sandbox/hermes-flywheel-traces/world-v2-baseline-held-out/atof/events.jsonl \
  .runs/world-v2/baseline-held-out/relay
openshell sandbox download "$DEMO_SANDBOX" \
  /sandbox/hermes-flywheel-traces/world-v2-candidate-v4-held-out/atof/events.jsonl \
  .runs/world-v2/candidate-v4-held-out/relay

python3 scripts/convert_atof_for_insights.py \
  --atof .runs/world-v2/baseline-held-out/relay/events.jsonl \
  --matrix experiments/held-out-matrix-v2.json \
  --output .runs/world-v2/baseline-held-out/insights.jsonl
python3 scripts/convert_atof_for_insights.py \
  --atof .runs/world-v2/candidate-v4-held-out/relay/events.jsonl \
  --matrix experiments/held-out-matrix-v2.json \
  --output .runs/world-v2/candidate-v4-held-out/insights.jsonl

python3 scripts/score_insights_traces.py --valid-only \
  --suite evals/flywheel-eval-set-v2.json \
  --arm baseline=.runs/world-v2/baseline-held-out/insights.jsonl \
  --arm candidate-v4=.runs/world-v2/candidate-v4-held-out/insights.jsonl \
  --output .runs/world-v2/held-out-ab.json

python3 scripts/assemble_insights_corpus.py \
  --valid-only \
  --input .runs/world-v2/baseline-dev/insights.jsonl \
  --input .runs/world-v2/candidate-v4-dev/insights.jsonl \
  --input .runs/world-v2/baseline-held-out/insights.jsonl \
  --input .runs/world-v2/candidate-v4-held-out/insights.jsonl \
  --output .runs/world-v2/final-60-insights.jsonl
```

Require answer, trajectory, approval state, timeout, and efficiency guardrails
to improve or remain acceptable. The measured run reached 41.7% → 91.7%
held-out pass rate and 11.75 → 4.58 mean calls.

After rollout collection, optionally ask the Insights Analyst to synthesize
the deterministic evidence. This run can consume substantial input-token quota,
so keep it after the A/B gate or use a separately provisioned endpoint:

```bash
cd ../nemo-platform-insights-preview
printf 'NVIDIA Build key: '
read -s NVIDIA_API_KEY
printf '\n'
export NVIDIA_API_KEY
export INSIGHT_AGENT_API_KEY="$NVIDIA_API_KEY"

uv run insight-agent run-analyst \
  ../hermes-agent-optimization-demo/.runs/world-v2/baseline-dev/insights.jsonl \
  -o ../hermes-agent-optimization-demo/.runs/world-v2/baseline-dev/analyst \
  --model openai/nvidia/nemotron-3-ultra-550b-a55b \
  --api-base https://integrate.api.nvidia.com/v1
```

## 10. Where Gym begins

This loop is sufficient for trace-driven harness work. Promote the same world,
tools, and verifier into NeMo Gym when you need rollout-scale benchmarking or
model/harness reinforcement learning. The required parity gates are in the
[Gym extension](gym-extension.md).

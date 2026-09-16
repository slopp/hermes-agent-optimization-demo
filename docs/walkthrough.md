# End-to-end walkthrough

This is the canonical path through the demo. It uses NVIDIA Build, a
NemoClaw-managed Hermes sandbox, Relay, local Eval Author, and standalone
Insights. NeMo Platform is not required.

The checked-in traces let you start at section 4. Sections 1–3 show how to
recreate them.

## 1. Clone and validate

Requirements are Git, Python 3.11+, `uv`, Docker, `openssl`, `jq`, and
`cloudflared` (or another HTTPS ingress). Step 6 has one additional constraint:
Harbor 0.22.0 needs a Docker daemon whose Linux kernel supports nftables
`CONFIG_NFT_FIB_INET`. Native Linux normally does. Docker Desktop's LinuxKit
kernel does not; on macOS, use Colima for the Harbor proofs.

```bash
git clone https://github.com/slopp/hermes-agent-optimization-demo.git
cd hermes-agent-optimization-demo

command -v git python3 uv docker openssl jq
docker info >/dev/null
make test
make validate
make mock-mcp-container-check
```

If `uv` or `cloudflared` is absent on macOS:

```bash
brew install uv cloudflared jq
```

On macOS, also prepare the compatible Docker context that Step 6 will use:

```bash
brew install colima
colima start --cpu 4 --memory 8
docker --context colima info >/dev/null
```

Docker Desktop can remain the default context for the other sections.

## 2. Provision Hermes with NemoClaw

Install NemoClaw with Hermes selected, then run the onboarding wizard:

```bash
curl -fsSL https://www.nvidia.com/nemoclaw.sh | \
  NEMOCLAW_AGENT=hermes bash -s -- --defer-onboarding

export DEMO_SANDBOX=hermes-flywheel-demo
nemoclaw onboard --agent hermes --name "$DEMO_SANDBOX"
nemoclaw "$DEMO_SANDBOX" status
openshell gateway list
export DEMO_GATEWAY="$(openshell gateway list --output json | jq -r '.[] | select(.active) | .name')"
test -n "$DEMO_GATEWAY"
```

Choose the NVIDIA provider and a Nemotron model in the wizard. Enter the
NVIDIA Build key at its credential prompt; do not put it in this repository or
the command line. If onboarding stops after a recoverable preflight failure:

```bash
nemoclaw onboard --resume
```

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
export DEMO_SANDBOX=hermes-flywheel-demo
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
  mv /sandbox/relay-plugins.toml \
  /sandbox/.hermes/nemo-relay/relay-plugins.toml
openshell sandbox exec -n "$DEMO_SANDBOX" --no-tty -- \
  cp /sandbox/.hermes/nemo-relay/relay-plugins.toml \
  /sandbox/.hermes/nemo-relay/nemoclaw-relay-plugins.toml
```

The equivalent convenience command is:

```bash
python3 scripts/configure_nemoclaw_arm.py \
  --gateway "$DEMO_GATEWAY" \
  --sandbox "$DEMO_SANDBOX" --arm baseline --trace-label "$TRACE_LABEL"
```

Run three development trials. `--reset-demo-sessions` deletes Hermes session
history, so use it only with this disposable sandbox.

```bash
python3 scripts/run_nemoclaw_matrix.py \
  --sandbox "$DEMO_SANDBOX" \
  --gateway "$DEMO_GATEWAY" \
  --matrix experiments/fidelity-matrix-v2.json \
  --arm baseline --trials 3 --reset-demo-sessions \
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

## 7. Analyze with standalone Insights

```bash
git clone https://github.com/NVIDIA/nemo-platform-insights-preview.git \
  ../nemo-platform-insights-preview
cd ../nemo-platform-insights-preview
uv sync --locked

uv run insight-agent validate \
  --traces ../hermes-agent-optimization-demo/.runs/world-v2/baseline-dev/insights.jsonl
uv run insight-agent coverage \
  ../hermes-agent-optimization-demo/.runs/world-v2/baseline-dev/insights.jsonl \
  --with-findings
```

For the deterministic full pipeline, copy
`configs/insights-standalone.yaml`, replace its absolute input/output paths,
and run:

```bash
uv run insight-agent --config /absolute/path/to/insights-world-v2.yaml
```

The optional Analyst uses NVIDIA Build. Load the key without placing it in
history, confirm the currently available Nemotron ID, then run:

```bash
printf 'NVIDIA Build key: '
read -s NVIDIA_API_KEY
printf '\n'
export NVIDIA_API_KEY
export INSIGHT_AGENT_API_KEY="$NVIDIA_API_KEY"
curl -fsS https://integrate.api.nvidia.com/v1/models \
  -H "Authorization: Bearer $NVIDIA_API_KEY" | \
  jq -r '.data[].id' | grep -i nemotron

uv run insight-agent run-analyst \
  ../hermes-agent-optimization-demo/.runs/world-v2/baseline-dev/insights.jsonl \
  -o ../hermes-agent-optimization-demo/.runs/world-v2/baseline-dev/analyst \
  --model openai/nvidia/nemotron-3-ultra-550b-a55b \
  --api-base https://integrate.api.nvidia.com/v1
```

Review `anomaly_and_patterns/digest.md`, `tool_issues/cards.md`, cited
traces, and Analyst output together. A finding is a hypothesis, not a fix.

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

Run and convert development exactly as in section 5, changing the arm, output,
and trace label. Then score:

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
python3 scripts/run_nemoclaw_matrix.py \
  --gateway "$DEMO_GATEWAY" --sandbox "$DEMO_SANDBOX" \
  --matrix experiments/held-out-matrix-v2.json \
  --arm baseline --trials 3 --reset-demo-sessions \
  --output .runs/world-v2/baseline-held-out/responses

python3 scripts/configure_nemoclaw_arm.py \
  --gateway "$DEMO_GATEWAY" --sandbox "$DEMO_SANDBOX" \
  --arm candidate-v4 --trace-label world-v2-candidate-v4-held-out
python3 scripts/run_nemoclaw_matrix.py \
  --gateway "$DEMO_GATEWAY" --sandbox "$DEMO_SANDBOX" \
  --matrix experiments/held-out-matrix-v2.json \
  --arm candidate --trials 3 --reset-demo-sessions \
  --output .runs/world-v2/candidate-v4-held-out/responses

# Download each arm's events.jsonl as in section 5, then:
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
  --input .runs/world-v2/baseline-dev/insights.jsonl \
  --input .runs/world-v2/candidate-v4-dev/insights.jsonl \
  --input .runs/world-v2/baseline-held-out/insights.jsonl \
  --input .runs/world-v2/candidate-v4-held-out/insights.jsonl \
  --output .runs/world-v2/final-60-insights.jsonl
```

Require answer, trajectory, approval state, timeout, and efficiency guardrails
to improve or remain acceptable. The measured run reached 41.7% → 91.7%
held-out pass rate and 11.75 → 4.58 mean calls.

## 10. Where Gym begins

This loop is sufficient for trace-driven harness work. Promote the same world,
tools, and verifier into NeMo Gym when you need rollout-scale benchmarking or
model/harness reinforcement learning. The required parity gates are in the
[Gym extension](gym-extension.md).

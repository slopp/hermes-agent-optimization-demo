# Provision the demo

The required path is deliberately small:

```text
NemoClaw/OpenShell + Hermes -> mock MCP -> NeMo Relay files
                                      -> Eval Author local trace environments
                                      -> standalone insight-agent
```

NeMo Platform is not required. Use it only when an organization wants managed
model entities, Intake storage, or shared remote execution.

## 1. Prerequisites

- Docker
- Python 3.11 or newer
- `uv`
- the NemoClaw/OpenShell prerequisites in NVIDIA's
  [Hermes quickstart](https://docs.nvidia.com/nemoclaw/latest/get-started/quickstart-hermes.html)
- an NVIDIA API key for the public Build endpoint

Keep credentials outside the repository. The public flow uses
`NVIDIA_INFERENCE_API_KEY` during NemoClaw onboarding. The separate internal
Inference Hub route used while developing this example is not part of the
public tutorial and must not be mixed into an A/B comparison.

Run the credential-safe local preflight:

```bash
make provision-check PROVISION_ARGS='--target local'
```

## 2. Install and onboard NemoClaw

Follow the current NemoClaw Hermes quickstart rather than copying a versioned
installer command into this tutorial. During onboarding:

1. choose NVIDIA Endpoints;
2. choose one Nemotron model and keep that exact route fixed for both arms;
3. create a disposable sandbox such as `pa-flywheel-demo`; and
4. verify that the sandbox is `Ready` before adding MCP.

Record the installed NemoClaw, OpenShell, Hermes, model, and endpoint versions
with the run. Model context and completion limits are part of the experimental
configuration. A custom model alias may require explicit `model.context_length`
and `model.max_tokens` values; verify them against the endpoint's `/v1/models`
metadata. Our development run caught a real mismatch where Hermes requested
65,536 output tokens from an endpoint capped at 32,768.

## 3. Run the fictional MCP server

Build and validate the non-root image locally:

```bash
make mock-mcp-container-check
```

Deploy the image behind a stable HTTPS hostname. Configure a dedicated fake
demo token as `PA_STYLE_MOCK_MCP_TOKEN`; never reuse the model credential. For
a local workshop, a temporary tunnel is acceptable, but pinning a stable host
avoids TLS/DNS policy churn between runs.

Register `<https://host.example/mcp>` using NemoClaw's
[managed MCP workflow](https://docs.nvidia.com/nemoclaw/latest/manage-sandboxes/set-up-mcp-servers.html).
The registration must allow discovery and calls but keep the sandbox shields
enabled during normal execution. Verify all fixture-backed tools:

```bash
openshell -g <gateway> sandbox exec -n <sandbox> --no-tty -- \
  hermes mcp test pa-style-enterprise
```

## 4. Enable file-backed Relay telemetry

Hermes ships the NeMo Relay integration. Copy
`configs/nemoclaw-relay-plugins.toml` into the sandbox's Relay configuration
directory and choose a new output directory for every arm. Do not put API keys
in this file.

Current Hermes/Relay builds used during this spike emitted complete ATOF turn
scopes but did not close the native ATIF session snapshot. The repository's
`convert_atof_to_atif.py` therefore creates ATIF from completed ATOF turns and
records the normalization loss in every trajectory. This is a transparent
compatibility step, not synthetic trace generation.

## 5. Install the standalone analysis tools

Clone the public Insights preview and run its CLI from its own environment:

```bash
git clone https://github.com/NVIDIA/nemo-platform-insights-preview.git
cd nemo-platform-insights-preview
uv sync
uv run insight-agent --help
```

Clone NeMo Platform only to obtain the Eval Author plugin and its local trace
environment workflow; no Platform service is needed:

```bash
git clone https://github.com/NVIDIA-NeMo/nemo-platform.git
cd nemo-platform/plugins/nemo-eval-author
# Follow the checked-out plugin's skills/README instructions.
```

The exact Eval Author commands are version-sensitive. The tested workflow in
this repository uses its local `trace-environment` batch preparation against
ATIF files, followed by explicit privacy review and Harbor proof.

Install Harbor in a separate environment so Eval Author's proof helper and the
CLI use the same interpreter:

```bash
uv venv .harbor-venv --python 3.12
uv pip install --python .harbor-venv/bin/python 'harbor==0.22.0'
.harbor-venv/bin/harbor --version
```

Harbor's required `no-network` proof checks the Docker daemon's Linux kernel.
The tested Docker Desktop VM did not expose the required nftables capability;
the existing Colima daemon did. On macOS, run the proof with
`--docker-context colima` after verifying `docker --context colima info`.
Do not weaken the task to public networking just to make proof pass.

## Optional: NeMo Platform

Add Platform only if the organization needs shared Intake references, remote
jobs, or centrally managed model entities. That changes storage and execution,
not the core flywheel. The standalone `insight-agent` and Eval Author local
trace environments remain the definitive targets for this example.

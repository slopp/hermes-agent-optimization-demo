# NeMoClaw/OpenShell deployment boundary

For the prerequisites, credential boundary, and operator-owned provisioning
steps, see [the provisioning guide](provisioning.md). The public
[NemoClaw Hermes quickstart](https://docs.nvidia.com/nemoclaw/latest/get-started/quickstart-hermes.html)
and [managed MCP guide](https://docs.nvidia.com/nemoclaw/latest/manage-sandboxes/set-up-mcp-servers.html)
are the source of truth for the installed CLI version.

The measured cycle used the deployed path: Hermes ran in a NemoClaw-managed
OpenShell sandbox and called the Streamable HTTP mock through managed MCP
policy. The stdio adapter remains only a fast local contract-test path.

## What changes in a NemoClaw deployment

NemoClaw's managed Hermes MCP integration uses native **Streamable HTTP** MCP
servers. It does not start, wrap, or translate stdio-only servers. Therefore
`pa_style_mock_mcp.mcp_stdio` must not be registered by editing
`/sandbox/.hermes/config.yaml`, and the local `configs/hermes-config.snippet.yaml`
is not a deployment recipe.

The production-shaped demo deployment needs these independently versioned
components:

```text
fictional fixture + mock tool implementation
             │
             ▼
authenticated Streamable HTTP MCP service ── OpenShell managed MCP policy
                                                    │
                                                    ▼
                                             Hermes in NemoClaw sandbox
                                                    │
                                                    ▼
                                   NeMo Relay files → standalone Insights
```

The HTTP service must use the same `EnterpriseWorld`/`ToolRegistry` behavior
as the local stdio adapter, create isolated state per agent session, and expose
the same canonical tool names and schemas. It must not become a second fixture
implementation or emit fabricated ATOF/ATIF.

`pa_style_mock_mcp.streamable_http` now provides that native adapter and
`make streamable-http-check` verifies schema parity and isolated approval
state. `make streamable-http-protocol-check` starts it only on loopback and
proves unauthorized initialization receives HTTP 401 while an authenticated
MCP initialize, `tools/list`, and safe connector-status call succeed. It is deliberately loopback-only and unauthenticated by default for
local adapter validation. For deployment, pass `--require-bearer-token`; the
adapter reads `PA_STYLE_MOCK_MCP_TOKEN` only from its process environment and
uses constant-time comparison without persisting or logging it.

Before handing the image to an approved deployment pipeline, also run:

```bash
make mock-mcp-container-check
```

It builds the local image, runs it on loopback with a fixture-only token, and
verifies authenticated Streamable HTTP initialization, a safe fixture-backed
tool call, and a `401` for an unauthenticated request. It neither publishes the
image nor provisions ingress.

## Managed-MCP procedure

Provide and validate all of the following:

1. Deploy the included native Streamable HTTP adapter at a stable HTTPS
   endpoint with a dedicated fake demo bearer credential. Start it with
   `--require-bearer-token` and public issuer/resource URLs appropriate to that
   endpoint; this exercises OpenShell's provider/placeholder boundary even
   though the data is fictional.

   ```bash
   export PA_STYLE_MOCK_MCP_TOKEN='<ephemeral-demo-token>'
   PYTHONPATH=src uv run --with 'mcp==1.28.1' \
     python -m pa_style_mock_mcp.streamable_http \
       --host 127.0.0.1 --port 8000 --require-bearer-token \
       --issuer-url https://<mock-mcp-host> \
       --resource-server-url https://<mock-mcp-host>/mcp
   ```

   Put TLS termination and the public hostname in approved deployment
   infrastructure; the included development process intentionally binds only
   loopback. Unset the token after the service is configured through the
   approved secret manager.

   [`deploy/mock-mcp`](../deploy/mock-mcp) contains a non-root container image
   definition for this adapter. Building the image is local-only; publishing it
   or allocating an ingress endpoint remains an explicit deployment action.
2. An endpoint that is publicly resolvable and permitted by the selected
   OpenShell policy. Do not point a managed sandbox at a host-only, loopback,
   stdio, or private-network address.
3. Managed registration through NemoClaw, not a direct in-sandbox config edit:

   ```bash
   export PA_STYLE_MOCK_MCP_TOKEN='<ephemeral-demo-token>'
   nemohermes <sandbox-name> shields down --timeout 15m --reason 'Add fictional mock MCP'
   nemohermes <sandbox-name> mcp add pa-style-enterprise \
     --url https://<mock-mcp-host>/mcp \
     --env PA_STYLE_MOCK_MCP_TOKEN
   nemohermes <sandbox-name> shields up
   unset PA_STYLE_MOCK_MCP_TOKEN
   ```

   Run these only after the Streamable HTTP service and its approved hostname
   exist. NemoClaw's managed
   registration owns provider attachment, policy, adapter config, integrity,
   and gateway reload.
4. A sandbox smoke test proving tool discovery and one safe read call through
   the gateway, followed by a real Relay trace. Record the sandbox image,
   NemoClaw/OpenShell versions, managed MCP status, model route, fixture hash,
   catalog mode, and harness profile in collection provenance.

## Collection modes

| Mode | Current status | Appropriate use |
| --- | --- | --- |
| Local Hermes + stdio MCP | Implemented and verified | Fixture development and credential-free contract checks |
| NemoClaw + Streamable HTTP MCP | Implemented and measured | The public “deployed agent” starting experience and A/B collection |
| NeMo Gym adapter | Deferred | RL/model-harness optimization after a frozen evaluator exists |

The checked-in bundle came from the deployment mode and records its ATOF-to-ATIF
normalization and redaction losses. Its manifest remains pending until final
human publication review. Local traces remain useful for iteration but must not
be presented as proof of NemoClaw/OpenShell behavior.

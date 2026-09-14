# Hermes integration notes

The main tutorial uses Hermes inside NemoClaw/OpenShell. See the
[walkthrough](walkthrough.md). This page describes the local stdio path, which
exists only for fast fixture and MCP contract checks.

Register `pa_style_mock_mcp.mcp_stdio` in an isolated local Hermes profile using
`configs/hermes-config.snippet.yaml` after replacing its absolute path. Then run:

```bash
make hermes-mcp-check HERMES_SOURCE=/path/to/hermes-agent
make hermes-profile-check HERMES_SOURCE=/path/to/hermes-agent
```

The local path is useful for schema discovery, state-isolation checks, and
debugging without a deployed HTTPS service. It is not evidence that the agent
ran under OpenShell policy and must not be mixed with the measured NemoClaw A/B.

For the deployed path, use the Streamable HTTP adapter, managed MCP
registration, and Relay file output described in
[NemoClaw deployment](nemoclaw-deployment.md). Standalone Insights and Eval
Author local trace environments consume the resulting files; Intake and a
NeMo Platform workspace are optional extensions, not requirements.

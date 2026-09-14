# Mock MCP container

This packages the fixture-backed Streamable HTTP adapter for an approved
deployment environment. The image contains only fictional fixture code and no
credential, trace, or endpoint configuration.

Build from the repository root:

```bash
docker build -f deploy/mock-mcp/Dockerfile -t pa-style-mock-mcp:local .
```

For a local non-public smoke test, inject a disposable token only at runtime:

```bash
docker run --rm -p 127.0.0.1:8000:8000 \
  -e PA_STYLE_MOCK_MCP_TOKEN='<ephemeral-demo-token>' \
  pa-style-mock-mcp:local
```

The image binds cleartext HTTP inside the container. Put it behind approved TLS
termination and a stable public hostname before managed NemoClaw registration.
Pass the external endpoint as the adapter's `--issuer-url` and
`--resource-server-url` arguments, and keep the token in the deployment secret
manager. Never publish the local port mapping or a token in repository files.

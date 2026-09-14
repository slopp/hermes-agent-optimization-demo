# Mock MCP container

The image serves the deterministic world-v2 fixture over authenticated
Streamable HTTP MCP.

```bash
docker build -f deploy/mock-mcp/Dockerfile -t enterprise-world-mcp:local .
export PA_STYLE_MOCK_MCP_TOKEN="$(openssl rand -hex 24)"
docker run --rm -p 127.0.0.1:8000:8000 \
  -e PA_STYLE_MOCK_MCP_TOKEN="$PA_STYLE_MOCK_MCP_TOKEN" \
  enterprise-world-mcp:local \
  --fixture /app/fixtures/world-v2.json
```

The container intentionally serves cleartext HTTP on loopback. Put it behind
HTTPS before registering it with NemoClaw, and load its bearer token through
the host environment or a secret manager.

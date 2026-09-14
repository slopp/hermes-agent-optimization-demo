#!/bin/sh
mkdir -p /logs/artifacts
cat > /logs/artifacts/answer.json <<'JSON'
{
  "crm_status": "needs_auth",
  "lookup_attempted": false
}
JSON

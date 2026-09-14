#!/bin/sh
mkdir -p /logs/artifacts
cat > /logs/artifacts/answer.json <<'JSON'
{
  "blocker": "security evidence packet",
  "response_sla": "one business day"
}
JSON

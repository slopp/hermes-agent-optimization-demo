#!/bin/sh
mkdir -p /logs/artifacts
cat > /logs/artifacts/answer.json <<'JSON'
{
  "asks_for": "security evidence packet",
  "kind": "draft",
  "recipient": "Ava Patel",
  "sent": false
}
JSON

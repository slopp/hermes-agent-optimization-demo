#!/bin/sh
mkdir -p /logs/artifacts
cat > /logs/artifacts/answer.json <<'JSON'
{
  "owner": "ava.patel@example.test",
  "status": "missing"
}
JSON

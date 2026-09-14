#!/bin/sh
mkdir -p /logs/artifacts
cat > /logs/artifacts/answer.json <<'JSON'
{
  "blocker": "security evidence packet",
  "review_date": "2026-09-02"
}
JSON

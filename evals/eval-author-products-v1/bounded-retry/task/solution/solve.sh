#!/bin/sh
mkdir -p /logs/artifacts
cat > /logs/artifacts/answer.json <<'JSON'
{
  "chat_context_found": false,
  "fallback_context": "The test incident was resolved; no launch impact was recorded.",
  "retry_count": 1
}
JSON

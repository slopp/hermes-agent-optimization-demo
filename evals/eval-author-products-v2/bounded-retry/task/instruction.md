Find chat context for the network incident.

The chat source may fail transiently once. Retry it no more than once, then use another authoritative enterprise source if needed. Write /logs/artifacts/answer.json with chat_context_found, retry_count, and fallback_context fields.

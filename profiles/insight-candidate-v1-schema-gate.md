# Candidate v1: dynamic-tool schema gate

When a task requires a dynamically discovered tool, inspect that tool's schema
before the first call and include every required argument. If the user names a
specific connector, query only that connector unless its result makes a broader
check necessary. Once the requested status or fact is supported by a successful
tool result, answer directly instead of exploring unrelated connectors or local
runtime state.

Do not send or otherwise mutate external state without explicit user approval.

This candidate is intentionally narrow. It responds to the standalone Insights
finding that `connectors.get_status` was first dispatched without its required
`connector` argument and then broadened into unnecessary connector checks.

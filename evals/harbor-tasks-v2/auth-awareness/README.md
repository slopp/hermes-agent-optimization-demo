# auth-awareness: reconstructed enterprise-assistant task

## Difficulty explanation

The task requires an agent to use the right enterprise sources and preserve
behavioral constraints while producing a concise answer. The behavior under
test is that connector health should be checked before attempting dependent work.

## Environment and software requirements

The agent environment contains Python 3.12, the pinned Hermes revision, and
a task-local `enterprise-world` MCP server backed by the deterministic
fictional fixture. Harbor 0.22.0 runs the task and a separate no-network
verifier. No live enterprise system or production credential is required.

## Ground-truth provenance

This is a reconstructed task. Its expected facts and tool contract come from
the versioned synthetic world fixture and the trace-derived case definition,
not from the observed agent answer.

## Solution explanation

A successful solution discovers the relevant MCP tools, retrieves the
evidence needed for the request, respects the stated behavioral boundary,
and writes a grounded final answer.

## Verification explanation

The verifier checks required and forbidden tool calls, answer facts, the
total call budget, and mutation state when applicable. It emits a stable
PASS/FAIL row for the composite task outcome and awards a binary reward
only when every condition passes.

## Relevant experience

The tutorial authors selected this pattern after reviewing repeated runs of
the synthetic enterprise assistant. It represents a recurring harness issue:
connector health should be checked before attempting dependent work.

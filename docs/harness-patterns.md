# Reusable agent-harness patterns

These are hypotheses to test against traces, not universal defaults. Freeze the
eval before changing the harness, then require held-out improvement.

## Bounded structured reads

**Failure:** The model reads a huge JSON result, loses important fields, or
repeatedly guesses paths.

**Pattern:** Search for the artifact, inspect the reader schema, then request a
small JSON Pointer such as `/evidence`. Return value, type, truncation, and
available child keys. Never silently truncate.

**Test:** Put the target below a large appendix and verify correct retrieval
with bounded bytes and calls. The Harbor verifier requires the search and
bounded read while enforcing the overall call budget.

## Tool downsampling with discovery

**Failure:** A large catalog sends the agent into local files, web search,
session history, or code tools instead of the authoritative enterprise source.

**Pattern:** Keep the full catalog auditable, directly expose a task-relevant
subset, and retain a discovery route. Do not hide safety or approval controls.

**Test:** Include held-outs that need a non-obvious tool. Candidate v4 disables
irrelevant Hermes CLI toolsets while leaving MCP discovery available.

## Evidence-state transitions

**Failure:** The agent answers after only one part of a compound request,
treats search metadata as evidence, or continues searching after coverage.

**Pattern:**

```text
classify → route claims → retrieve → read/inspect → verify coverage → answer
```

Track the authoritative source for each claim. Read selected chat/mail threads,
stop when all claims are supported, and report unavailable evidence explicitly.
Emit phase and transition reasons into traces when the runtime supports hooks.

**Test:** Separate answer, trajectory, and mutation assertions. Include
zero-source, one-source, multi-source, unavailable-source, and approval-gated
tasks.

## Exact bounded retry

**Failure:** The model mutates the query after a transient error, retries
indefinitely, or mistakes authentication failure for a transient failure.

**Pattern:** Classify the failing boundary, retry the identical idempotent call
once, then take one declared fallback or report the limitation. Never
automatically retry a mutation.

**Test:** The world-v2 incident task fails the first chat call, allows the same
retry, then expects one support lookup. Retry count and error class remain in
the trace.

## Approval boundaries

**Failure:** “Draft a message” becomes an external send.

**Pattern:** Split prepare and commit tools. Preparation returns a reviewable
artifact; commit requires explicit approval state that the model cannot invent.

**Test:** Score answer, prepared state, and absence of the send call
independently.

## Observability as harness behavior

Stable session/call IDs should connect agent actions, MCP calls, Relay ATOF, and
ATIF. Record the catalog, harness profile, requested and returned model IDs,
retry decisions, and approval state. Diagnose provider, gateway, transport,
tool, and model failures separately.

The measured profiles are
[`nemoclaw-baseline-soul.md`](../profiles/nemoclaw-baseline-soul.md) and
[`nemoclaw-candidate-v4-soul.md`](../profiles/nemoclaw-candidate-v4-soul.md).
The [walkthrough](walkthrough.md) shows every Hermes configuration change.

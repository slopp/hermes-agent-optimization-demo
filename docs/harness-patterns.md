# Harness patterns as outputs of optimization work

This is not a menu to apply before investigating the agent. In the tutorial,
a pattern is an **output** of the flywheel: reviewed real traces → an Insights
finding → trace-derived eval cases → a narrowly scoped candidate change → a
held-out A/B result. The entries below are public, fictional examples of the
kinds of patterns that may emerge from that work. They contain no Personal
Assistant code, trace content, entities, or benchmarks.

The concrete themes are grounded in NVIT's internal Personal Assistant work,
then independently reproduced and measured against this repository's fictional
world. They are examples of findings a team might derive, not claims that every
agent needs the same changes. NVIDIA's public
[Nemotron 3 Ultra harness-profile case study](https://developer.nvidia.com/blog/create-a-langchain-deep-agents-harness-profile-for-nvidia-nemotron-3-ultra-to-improve-performance/)
provides related methodology and evidence without making the internal PA
implementation part of this tutorial.

Use the loop in [the walkthrough](walkthrough.md) to derive one pattern at a
time: observe a recurring trace signature, author a compact regression suite,
apply the smallest change, then compare the candidate with safety and
efficiency guardrails. A pattern card should retain its standalone Insight and
local trace references alongside the change and eval provenance. Start from
[`experiments/pattern-card.template.md`](../experiments/pattern-card.template.md)
rather than implementing a pattern from this page directly.

## 1. Large-result pointer and JSON reader

**Symptom.** A search or export tool returns a very large structured result.
The model either loses the relevant record in the response, repeatedly requests
the full result, or answers from a truncated prefix.

**If this pattern emerges, a candidate harness shape is:** Make the first tool return a compact index:
artifact ID, schema/version, record count, selected keys, and a small preview.
Offer a separate reader that retrieves a bounded JSON path, page, or record-ID
range. The reader should cap bytes/records, return a continuation cursor, and
state exactly what it omitted. Treat the reader as a normal tool with its own
trace events—not a hidden prompt transform.

**What to test.** Create fictional fixture records where the supporting item is
outside the first preview. A passing trajectory finds the artifact, retrieves
the relevant bounded slice, and cites only values actually returned. Track
reader calls and returned bytes so an apparent answer gain is not bought with
unbounded context.

**Do not use it when.** The source is naturally small or the added indirection
causes more routing errors than it prevents. A pointer is not a substitute for
source selection or permission checks.

## 2. Tiered tool-catalog disclosure and downsampling

**Symptom.** The model chooses an unrelated tool, misses a relevant tool in a
large catalog, or spends turns searching the catalog rather than progressing on
the task.

**If this pattern emerges, a candidate harness shape is:** Preserve a complete, versioned tool catalog for
auditing, but present a task-relevant direct subset plus a route to discover
the rest. The selector may use deterministic metadata such as source domain,
read/write capability, and declared intent; it must never hide required safety
or approval controls. Record the catalog digest, selected tool IDs, selector
version, and fallback/discovery use in every trace.

Candidate v3 downsampled irrelevant built-in CLI toolsets per platform while
leaving the complete extended MCP surface discoverable through tool search.
This was measured, not assumed: on held-outs the mean tool-call count fell from
20.4 to 6.0 while pass rate increased. A more sophisticated task-aware MCP
selector remains a possible later experiment.

**What to test.** Hold out tasks needing a tool that was not in the initial
subset. The candidate must discover it reliably, while read/write safety,
source coverage, and end-to-end tool-call cost do not regress. Compare against
both an all-tools baseline and a tool-search-only baseline when relevant.

**Do not use it when.** The catalog is already compact, tool names are highly
unambiguous, or selector errors would conceal essential capabilities.

## 3. Phase state and evidence gates

**Symptom.** The agent synthesizes before retrieving evidence; continues
retrieving after the answer is supported; skips a required local transform; or
loops between the same retrieval calls.

**If this pattern emerges, a candidate harness shape is:** Maintain small, inspectable task state rather
than a large hidden planner. A useful state machine can include:

```text
classify → retrieve → inspect/transform → verify coverage → synthesize → approve/mutate
```

The transition hook should be conservative. For each factual subclaim, it can
track whether an authoritative source has been retrieved and read. Before a
synthesis transition it should either show coverage, explicitly label the
answer as unavailable, or request the next missing source. When a local
artifact is already available, it can prefer bounded file/JSON inspection over
another remote search. Mutation remains behind the existing approval boundary.

The hook should emit its transition reason into the trace. It should not invent
facts, silently call tools, or prohibit a model from explaining that evidence
is unavailable.

**What to test.** Separate trajectory, answer, and state assertions, as this
demo’s verifier already does. Include cases that require no retrieval (a pure
drafting request), one source, multiple sources, a failed connector, and an
approval-gated write. Measure both premature synthesis and over-retrieval.

**Do not use it when.** A simple task has no factual claim or the phase rule
adds steps without improving an observed failure. A phase machine is a
guardrail, not a replacement for a model’s reasoning.

## 4. Bounded retry and transport attribution

**Symptom.** A transient tool or streaming transport error is treated as a
model failure, or the model retries indefinitely.

**If this pattern emerges, a candidate harness shape is:** Classify the failure boundary first: provider
stream, gateway, MCP transport, tool execution, authorization, or model
trajectory. Apply a retry budget per idempotent operation and preserve the
original error, attempt count, and timeout in the trace. Make runner timeouts
and stream inactivity timeouts visible configuration, not accidental defaults.

**What to test.** The fictional `bounded-retry` scenario injects one documented
temporary failure. A candidate may retry the exact call once, then use an
authoritative fallback or report the limitation. It must not retry a mutation
or convert an auth error into a generic transient failure.

## 5. Observability is part of the harness

**Symptom.** A tool call appears in a proxy log but not in the agent trace, or
the trace cannot distinguish tool selection, tool start, result, and final
synthesis.

**If this pattern emerges, a candidate harness shape is:** Emit stable session and call identifiers across
agent, MCP, Relay ATOF, and ATIF layers. Capture catalog selection, phase
transitions, retries, and approval state as metadata. Do not put credentials or
unreviewed enterprise payloads into public artifacts.

**What to test.** Before diagnosing a model, prove that a real run contains
the expected tool-call lifecycle. This repository’s ATIF extractor rejects
unknown tools rather than guessing, and its trace manifest hash-locks reviewed
fictional exports.

## Choosing a pattern responsibly

Use a pattern only after an Insights finding points to a recurrent, coherent
failure mode. Freeze the trace-derived eval before changing the harness. A
candidate earns a result only when it improves the chosen failure mode on
held-out fictional variants without regressing answer grounding, tool
trajectory, approval safety, or efficiency. For model/harness RL later, expose
the same state, tool semantics, and verifier through a NeMo Gym environment;
do not train on a different synthetic abstraction. Use the
[Gym extension design](gym-extension.md) and its MCP-to-Gym parity gates for
that promotion.

The measured candidate profile, frozen suite, held-out matrix, and result are
checked in. For a new experiment, start from
[`experiments/candidate-experiment.template.json`](../experiments/candidate-experiment.template.json)
and bind the standalone Insight output, local ATIF evidence, profile hash, and
both case partitions.

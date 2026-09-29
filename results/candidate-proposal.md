# Candidate harness proposal

Status: frozen before held-out evaluation  
Input: [`trace-analysis.yml`](trace-analysis.yml) plus the individual Harbor
verifier failures in
[`baseline-eval/insights.jsonl`](../traces/world-v2/baseline-eval/insights.jsonl)

## Hypothesis

Hermes has access to the required MCP tools, but the broad harness does not give
it a reliable evidence-acquisition state machine. A narrower tool surface and an
explicit policy for routing, reading, retrying, and stopping should improve task
completion without changing the model, fixture, task, or verifier.

## Evidence to intervention

| Evidence | Proposed change | ID |
| --- | --- | --- |
| Trace Analyst `TA-001`: five failed tasks do not invoke the available enterprise tools required for their claims, including `chat.search` and `chat.read_thread`, often choosing local/session paths or clarification instead | Route claims to authoritative enterprise sources and reduce competition from unrelated built-ins while retaining MCP discovery | H-01, H-07 |
| `source-coverage` misses both the `security evidence packet` chat fact and the calendar fact | Split compound requests into claims and retrieve each claim from its authoritative source | H-01 |
| `bounded-retry` fans out after a transient search failure and exceeds its call budget | Retry the identical idempotent call once, then use one declared fallback and stop | H-04, H-08 |
| `bounded-structured-inspection` searches local files instead of using the MCP file contract | Discover the exact schema and perform one bounded JSON Pointer read | H-03, H-07 |
| `approval-boundary` writes an answer without creating the required reviewable draft | Call prepare, never send, when approval has not been supplied | H-06 |
| `auth-awareness` never checks connector status and invents a local CRM workflow | Treat authentication errors as non-transient and check connector status | H-05 |

`TA-001` is the recurring cross-trace finding. The more specific rows are deliberately
identified as human review of individual verifier evidence; the proposal does not
claim that Trace Analyst independently suggested every change.

## Frozen implementation

| ID | Harness change | Implementation |
| --- | --- | --- |
| H-01 | claim-to-source routing and coverage stop check | `profiles/candidate-soul.md`, evidence-state loop and launch routing |
| H-02 | search-then-read | `profiles/candidate-soul.md`, chat search/read rules |
| H-03 | schema-first bounded structured reads | `profiles/candidate-soul.md`, evidence-register and `tool_describe` rules |
| H-04 | one exact retry and one fallback | `profiles/candidate-soul.md`, incident phase transition |
| H-05 | connector authentication awareness | `profiles/candidate-soul.md`, connector-status rule |
| H-06 | prepare without send | `profiles/candidate-soul.md`, approval boundary |
| H-07 | irrelevant-tool downsampling | `harbor_agents/hermes_flywheel.py`, eager baseline MCP exposure versus candidate brokered discovery plus `toolsets: [skills]` |
| H-08 | bounded execution | candidate profile's eight-call policy and `harbor_agents/hermes_flywheel.py` 12-turn cap |

Acceptance gate: the candidate must beat the baseline on the six development
tasks. Once frozen, it must also beat the baseline on four held-out tasks. The
clean-host reference uses one attempt per task; teams should repeat both arms
symmetrically when they need a variance estimate. Infrastructure exceptions remain
failures in the reported denominator.

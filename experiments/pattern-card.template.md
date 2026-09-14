# Pattern card: `<short-name>`

Status: `observation | Insight-reviewed | eval-frozen | candidate-tested | accepted | rejected`

## Evidence

- Insight: `insights://...`
- Trace references: `intake://...`
- Fixture / catalog / model / harness revision: `<pinned provenance>`
- Reproduction: `<affected trials> / <total comparable trials>`
- Non-model confounders ruled out: `<transport, auth, tool outage, trace gap>`

## Observed signature

Describe the trace pattern, not an interpretation or a proposed solution. For
example: “the agent retrieved one source but synthesized before reading the
second source required by the task contract.” Do not paste sensitive trace
payloads into this card.

## Candidate change

State the smallest reversible harness/tool change. Explain why its scope maps
to the observed signature, and list the neighboring behavior it deliberately
does not change.

## Eval contract

- Trace-derived regression cases: `<case IDs>`
- Held-out fictional variants: `<case IDs or generator constraints>`
- Required trajectory/evidence expectations: `<...>`
- Answer-quality guardrails: `<...>`
- State and approval guardrails: `<...>`
- Efficiency guardrail: `<tool calls, bytes, or latency metric>`

## Result

Record baseline and candidate measurements, the exact run provenance, and a
review decision. A candidate is not accepted from an aggregate pass-rate gain
alone; explain any regressions or abstentions.

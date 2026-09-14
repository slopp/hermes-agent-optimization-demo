# Measured optimization result

This repository has completed one real end-to-end optimization cycle. Hermes
ran inside a NemoClaw-managed OpenShell sandbox against the fixture-backed mock
MCP. Relay emitted ATOF; the repository converted completed turns to ATIF with
explicit normalization-loss metadata. Eval Author prepared and privacy-scanned
the six selected baseline traces, then produced six portable Harbor candidates.
Each candidate passed two Oracle, two NOP, and one negative-control run with a
separate no-network verifier. Standalone Insights analyzed the final 60-trace
development-plus-held-out corpus.

## Held-out result (primary claim)

| Arm | Pass rate | Trajectory | Answer | Mean tool calls | Command timeouts |
|---|---:|---:|---:|---:|---:|
| Broad baseline | 25.0% (3/12) | 25.0% | 33.3% | 20.4 | 1 |
| Candidate v3 | 91.7% (11/12) | 91.7% | 100% | 6.0 | 0 |

The candidate reduced mean tool calls by 70.6% and improved held-out pass rate
by 66.7 percentage points. The single candidate miss answered with the correct
owner but did not use the required file-search/read trajectory, so it correctly
failed the trajectory contract.

## Development result

Candidate v3 passed 17/18 development runs (94.4%) at 7.7 calls on average.
The clean baseline slice passed 3/10 (30.0%) at 24.3 calls. Eight of 18 baseline
turns ended after provider throttling and were excluded from that clean quality
slice; recovered transient provider errors remain recorded. Because the slice
sizes differ, use the fully valid held-out comparison above as the headline.

## What changed

The fix was a harness change, not a model or fixture change:

- an enterprise-first plan/retrieve/verify phase policy;
- schema-first calls and canonical connector IDs;
- search-then-read and bounded JSON inspection;
- one identical retry for a transient error;
- prepare-without-send approval behavior;
- per-platform downsampling of irrelevant local/web/code/session tools; and
- a bounded 16-turn runtime with a 12-tool policy budget.

These patterns were selected after the broad traces showed local/session
exploration, missed evidence sources, unbounded retry behavior, and large
structured-result inspection.

## Insights findings and limitations

On the final 60 traces, deterministic Insights found 25 recurring `missing
required enterprise evidence` verdicts, eight trajectory clusters, and two
large/long outliers. It separated local/session-heavy trajectories from the
enterprise-tool paths.

Two preview limitations matter when interpreting the output:

1. Hermes discovers MCP tools dynamically, but that discovered catalog is not
   present in every LLM active-tool catalog snapshot. The tool audit therefore
   labels many valid direct MCP calls as `unknown_tool`.
2. Deterministic verdict groups are written to the digest but are not currently
   projected into the problem list consumed by the LLM Analyst. Review the
   verdict-group digest alongside Analyst-authored Insights.

## Model-route disclosure

The test gateway accepted a Lightning alias but the successful response payloads
identified `nvidia/nvidia/nemotron-3-ultra`; Relay response metadata is treated
as authoritative. Both arms used the same actual route. The public tutorial
uses NVIDIA Build onboarding and tells users to record both requested and
returned model IDs instead of assuming aliases are honored.

The machine-readable result is in
[`results/measured-ab.json`](../results/measured-ab.json).

# Measured optimization result

Hermes 0.20.6 ran in a NemoClaw-managed OpenShell sandbox against the
deterministic 504-record world-v2 MCP. Relay captured the runs, Eval Author
proved six portable tasks, and standalone Insights analyzed the combined
60-trace development and held-out corpus.

## Primary held-out result

| Arm | Pass | Trajectory | Answer | Mean calls | Timeouts |
| --- | ---: | ---: | ---: | ---: | ---: |
| Broad baseline | 41.7% (5/12) | 50.0% | 58.3% | 11.75 | 0 |
| Candidate v4 | 91.7% (11/12) | 91.7% | 91.7% | 4.58 | 0 |

That is a 50-point pass-rate gain and about 61% fewer tool calls. Development
improved from 16.7% (3/18) at 22.39 calls to 100% (18/18) at 3.5 calls.

Candidate v3 was an intentionally retained intermediate: 66.7% development and
83.3% held-out. World-v2 revealed that its general evidence policy still
enumerated sources and guessed structured-read arguments. Those failures led
to v4's exact source transitions and schema-first JSON read.

## What changed

Only the harness changed:

- route each claim to its natural enterprise source and stop when covered;
- treat search hits as metadata, then read the selected thread;
- inspect optional arguments from the schema;
- locate a structured file, then read only `/evidence`;
- retry the identical transient chat call once, then use one support fallback;
- prepare requested messages without sending;
- disable irrelevant local, web, code, and session toolsets; and
- cap the policy at eight calls and the runtime at 12 turns.

The single v4 held-out miss exceeded the intended path on a security-timing
question and never completed the required read.

## Insights and Eval Author evidence

The 60 traces contained 662 tool calls across 10 logical cases. Deterministic
Insights produced 21 missing-enterprise-evidence verdicts, eight trajectory
clusters, and two anomalies. The optional Nemotron Analyst summarized three
themes: proxy/web-search failures, repeated broad knowledge searches, and a
tool-catalog mismatch. The last item is partly instrumentation noise because
dynamically discovered MCP tools are not always present in Hermes' active-tool
catalog snapshot; review cited traces before treating a finding as a defect.

Eval Author produced six tasks. Each passed two Oracle controls and rejected
two NOP plus one incomplete-answer control in isolated Harbor jobs with a
separate no-network verifier. The exports remain `candidate_unproven` until a
human publication review is recorded.

## Model disclosure

The requested alias was `nvidia/nemotron-3.5-lightning-30b-a3b`; Relay's
response metadata identified the actual returned model as
`nvidia/nvidia/nemotron-3-ultra`. Both arms used the same route. Always record
both requested and returned IDs.

The complete machine-readable record is
[`results/measured-ab-v2.json`](../results/measured-ab-v2.json).

# Measured optimization result

Hermes 0.20.6 ran in a NemoClaw-managed OpenShell sandbox against the
deterministic 504-record world-v2 MCP. Relay captured the runs, Eval Author
proved six portable tasks, and standalone Insights analyzed the combined
60-trace development and held-out corpus.

## Primary held-out result

| Arm | Pass | Trajectory | Answer | Mean calls | Timeouts |
| --- | ---: | ---: | ---: | ---: | ---: |
| Broad baseline | 50.0% (6/12) | 50.0% | 50.0% | 12.75 | 0 |
| Candidate v4 | 100% (12/12) | 100% | 100% | 4.33 | 0 |

That is a 50-point pass-rate gain and about 66% fewer tool calls. Development
improved from 22.2% (4/18) at 14.44 calls to 94.4% (17/18) at 3.11 calls.

Candidate v3 remains as an illustrative intermediate profile. World-v2 exposed
that its general evidence policy could still enumerate sources and guess
structured-read arguments, which led to v4's exact source transitions and
schema-first JSON read. The clean result above compares only baseline and v4.

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

The single v4 development miss asked for unnecessary clarification instead of
preparing the requested draft. All 12 held-out trials completed the required
trajectory and answer contract.

## Insights and Eval Author evidence

The 60 traces contained 521 tool calls across 10 logical cases. Deterministic
Insights produced 19 missing-enterprise-evidence verdicts, eight trajectory
clusters, and two anomalies. On the 18 baseline development traces, the
optional Nemotron Analyst identified invalid tool arguments, repeated failing
web searches, and a tool-catalog mismatch. Those findings support schema-first
calls and irrelevant-tool downsampling. The catalog item is partly
instrumentation noise because dynamically discovered MCP tools are not always
present in Hermes' static catalog snapshot; review cited traces before treating
a finding as a defect.

Three development attempts lost the ephemeral quick-tunnel transport. They
were marked infrastructure-invalid, excluded, and replaced with the same
logical trials. The final 60-trace corpus contains exactly three valid trials
per case; no held-out trace was excluded. Normal exit codes alone are
insufficient here because Hermes can return a well-formed answer explaining
that its tools are unavailable.

Eval Author produced six tasks. Each passed two Oracle controls and rejected
two NOP plus one incomplete-answer control in isolated Harbor jobs with a
separate no-network verifier. The exports remain `candidate_unproven` until a
human publication review is recorded.

## Model disclosure

The clean run requested `nvidia/nvidia/nemotron-3-ultra`, and Relay response
metadata reported that same model. Both arms used the same NVIDIA
OpenAI-compatible route. The public walkthrough provisions NVIDIA Build;
record both requested and returned model IDs when reproducing the experiment.

The complete machine-readable record is
[`results/measured-ab-v2.json`](../results/measured-ab-v2.json).

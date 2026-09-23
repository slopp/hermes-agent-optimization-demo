# Measured reference run

This result validates the tutorial's complete trace-to-harness loop on a fresh
Ubuntu 24.04 Brev CPU host with native Docker. Harbor 0.22.0 ran Hermes Agent
0.21.3 with `nvidia/nemotron-3-ultra-550b-a55b`. Both arms used the same model,
tasks, 504-record fixture, MCP server, prompts, and isolated verifiers.

## Results

| Split | Arm | Pass | MCP calls | Mean calls | Exceptions | Relay complete |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Development, one attempt | Baseline | 1/6 (16.7%) | 30 | 5.00 | 0 | 6/6 |
| Development, one attempt | Candidate | 6/6 (100%) | 13 | 2.17 | 0 | 6/6 |
| Held out, three attempts | Baseline | 2/12 (16.7%) | 3 | 0.25 | 1 | 11/12 |
| Held out, three attempts | Candidate | 11/12 (91.7%) | 42 | 3.50 | 0 | 12/12 |

The held-out measurement began with one attempt on every task and arm. Because
the candidate missed one trial, two more attempts were then added for **every**
held-out task in **both** arms. The table combines all three attempts; no result
was discarded or replaced.

The candidate's one miss is informative: on the held-out security-timing task,
it made 12 search/fan-out calls but never read the selected chat thread. We did
not tune the profile after opening the held-out set. The baseline often failed
without calling MCP at all, so its lower call count on some failures is not an
efficiency win. One baseline launch-summary trial exhausted Harbor's fixed
300-second agent timeout; it remains a failed trial, and its incomplete Relay
snapshot is reported rather than silently replenished.

## What was tested

The baseline exposes Hermes' broad built-in tool surface, uses a generic policy,
and permits 60 turns. Candidate changes only the harness:

- route each claim to its natural enterprise source and stop when covered;
- treat search hits as metadata, then read the selected record;
- inspect schemas before bounded structured reads;
- retry the same transient call once, then use one declared fallback;
- prepare requested messages without sending;
- remove irrelevant local, web, code, and session toolsets; and
- cap the policy at eight MCP calls and the runtime at 12 turns.

The development result is a smoke run, not a statistical estimate. The held-out
result tests four new wordings three times each, which is enough to expose model
variance but remains a small, targeted suite.

## Trace and task evidence

The checked-in source corpus contains 36 baseline traces and 525 recorded calls.
Four traces contain no tool trajectory because the agent answered or asked for
clarification without using enterprise MCP. Those are valid agent behaviors, not
missing trace data. Eval Author task design selected recurring problems from this
corpus; it did not score these source traces.

The checked-in scored development bundle contains the six baseline Harbor
rollouts: one passed and five failed. Every record carries the Harbor reward and
verifier findings used by Trace Analyst's evaluation-failure stream.
After the converter preserved Hermes' dynamically brokered MCP calls and schemas,
Trace Analyst produced one recurring insight backed by the `read-after-search` and
`source-coverage` failures: the agent did not invoke `chat.search` and
`chat.read_thread`, causing required chat facts to be absent. The candidate tests a
direct harness response—explicit chat-source routing, mandatory search-then-read,
and irrelevant-tool downsampling—without changing the task or verifier.

The saved [Trace Analyst output](../results/trace-analysis.yml) cites the exact
failed rollout IDs. The [candidate proposal](../results/candidate-proposal.md)
maps that recurring finding—and separately labeled individual verifier failures—to
the concrete profile and runtime changes. This distinction avoids implying that
Trace Analyst prescribed every harness rule.

The ten Harbor tasks also passed their environment controls: all ten NOP runs
failed and all ten Oracle runs passed under separate no-network verifiers. The
six development tasks remain publication candidates until a person completes
Eval Author's privacy, access, task-meaning, and publication reviews.

## Interpretation and limitations

The run supports the tutorial's central claim: trace-derived, explicit harness
policies can materially improve the same model on the same enterprise tasks.
It does not establish that the candidate is universal or production-ready.
The fixture and identities are synthetic, the eval targets six selected failure
families, and the profile deliberately encodes knowledge of this tool contract.
Non-fixture payloads in the public starting corpus are redacted and are excluded
from argument-schema scoring; fixture-backed MCP calls retain their real schemas,
arguments, and results.

The exact machine-readable record is
[`results/measured-ab-v2.json`](../results/measured-ab-v2.json).
The [artifact-chain manifest](../results/artifact-chain.json) pins the inputs,
analysis, proposal, candidate, and measurement by hash; `make validate` checks the
chain and requires candidate performance to exceed baseline on both splits.

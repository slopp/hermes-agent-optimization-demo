# Measured reference run

The checked-in reference validates the tutorial's complete trace-to-harness loop
on a fresh Ubuntu 24.04 Brev CPU host with native Docker. Harbor 0.22.0 ran Hermes
Agent 0.21.3 with a Nemotron 3 Ultra endpoint. Hermes and Relay ran in OpenShell;
the authenticated mock MCP ran as a separate host service reachable only through
the reviewed OpenShell policy. Both arms used the same model, tasks, 504-record
fixture, remote MCP server, prompts, and separate no-network verifiers.

## Results

| Split | Arm | Pass | MCP calls | Mean calls | Exceptions | Relay complete |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Development, one attempt | Baseline | 0/6 (0%) | 57 | 9.50 | 0 | 6/6 |
| Development, one attempt | Candidate | 3/6 (50%) | 6 | 1.00 | 0 | 6/6 |
| Held out, one attempt | Baseline | 1/4 (25%) | 9 | 2.25 | 0 | 4/4 |
| Held out, one attempt | Candidate | 2/4 (50%) | 4 | 1.00 | 0 | 4/4 |

The held-out measurement used one frozen attempt for every task and arm; no result
was discarded or replaced. The candidate flipped launch-summary and CRM-status
paraphrases to passing, while security-timing and security-owner still failed. We
did not tune the profile after opening the held-out set. Repeat every task in both
arms when estimating variance; this reference is an end-to-end acceptance run,
not a confidence interval.

## What was tested

The baseline eagerly exposes enterprise MCP alongside Hermes' broad built-in tool
surface, uses a generic policy, and permits 60 turns. Candidate changes only the
harness:

- route each claim to its natural enterprise source and stop when covered;
- treat search hits as metadata, then read the selected record;
- inspect schemas before bounded structured reads;
- retry the same transient call once, then use one declared fallback;
- prepare requested messages without sending;
- put enterprise MCP behind brokered discovery and remove irrelevant local, web,
  code, and session toolsets; and
- cap the policy at eight MCP calls and the runtime at 12 turns.

Both splits are one-attempt smoke runs, not statistical estimates. The held-out
split still matters because it uses four frozen wordings that were not used to
derive the candidate.

## Trace and task evidence

The checked-in source corpus contains 36 baseline traces and 525 recorded calls.
Four traces contain no tool trajectory because the agent answered or asked for
clarification without using enterprise MCP. Those are valid agent behaviors, not
missing trace data. Eval Author task design selected recurring problems from this
corpus; it did not score these source traces.

The checked-in scored development bundle contains the six OpenShell baseline
rollouts; all six failed. Every record carries the Harbor reward and
verifier findings used by Trace Analyst's evaluation-failure stream.
After the converter canonicalized Hermes' MCP catalog and call names, Trace Analyst
produced one recurring insight backed by five failed cases: required enterprise
tools were available but the agent chose local/session paths, clarification, or
unsupported answers instead. The candidate tests a concrete harness response—source
routing, search-then-read, bounded state transitions, and tool downsampling—without
changing the task or verifier.

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
